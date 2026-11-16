"""
Provider-agnostic LLM calls for the v2 benchmark (D-12).

    result = call_llm(model_key, system_prompt, user_prompt, json_schema, condition)

`model_key` is an entry of config.V2_LLM_MODELS; its "provider" picks the adapter below.
`condition` ("A" / "B") selects that model's generation settings (e.g. thinking level).
Every adapter returns an LLMResult — never raises — so the calling script can log failures
uniformly. Error kinds:
    fatal      same failure on every call (billing, API disabled, bad key, unknown model) -> stop run
    retryable  rate limit / server busy / network -> wait and retry
    bad_output answer is not valid JSON -> retry, then record as error
Adding a provider = one adapter function + one config entry; prompts and schema stay identical.
"""

import itertools
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field

import config as C
from v2_common import friendly_api_error, is_fatal_error, load_env_key, stable_hash


@dataclass
class LLMResult:
    parsed: dict = None
    raw_text: str = None
    model_version: str = None
    prompt_tokens: int = None
    output_tokens: int = None
    thought_tokens: int = None
    latency_s: float = None
    error: str = None
    error_kind: str = None           # None | fatal | retryable | bad_output
    retry_after_s: float = None
    settings: dict = field(default_factory=dict)   # exact generation settings sent

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return asdict(self)


def call_llm(model_key: str, system_prompt: str, user_prompt: str, schema: dict, condition: str) -> LLMResult:
    cfg = C.V2_LLM_MODELS[model_key]
    adapter = _ADAPTERS.get(cfg["provider"])
    if adapter is None:
        return LLMResult(error=f"no adapter for provider '{cfg['provider']}'", error_kind="fatal")
    t0 = time.time()
    res = adapter(cfg, system_prompt, user_prompt, schema, condition)
    res.latency_s = round(time.time() - t0, 2)
    return res


def _parse_json(text: str):
    try:
        return json.loads(text), None
    except (TypeError, json.JSONDecodeError) as e:
        return None, f"invalid JSON: {e}"


# =====================================================================
#  Gemini (google-genai SDK)
# =====================================================================
_gemini_clients = {}
_client_lock = threading.Lock()          # one client per key, created once even with parallel workers


def _gemini(cfg, system_prompt, user_prompt, schema, condition) -> LLMResult:
    from google import genai
    from google.genai import types

    with _client_lock:
        if cfg["api_key_env"] not in _gemini_clients:
            _gemini_clients[cfg["api_key_env"]] = genai.Client(
                api_key=load_env_key(cfg["api_key_env"]),
                http_options=types.HttpOptions(timeout=C.V2_LLM_TIMEOUT_S * 1000))   # a stuck request is retried
    client = _gemini_clients[cfg["api_key_env"]]

    cond = cfg["conditions"][condition]
    thinking = types.ThinkingConfig(**cond) if cond else None
    settings = {"model": cfg["model_name"], "temperature": cfg["temperature"], **cond}
    gen_cfg = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        response_json_schema=schema,
        temperature=cfg["temperature"],
        thinking_config=thinking,
        # no tools / function calling: the model must answer from its own knowledge (also silences an SDK warning)
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    try:
        resp = client.models.generate_content(model=cfg["model_name"], contents=user_prompt, config=gen_cfg)
    except Exception as e:                                   # SDK raises for HTTP errors
        text = str(e)
        status = getattr(e, "code", None) or _status_from_text(text)
        if is_fatal_error(status or 0, text):
            kind = "fatal"
        elif status in (429, 500, 502, 503, 504) or "RESOURCE_EXHAUSTED" in text or "UNAVAILABLE" in text:
            kind = "retryable"
        elif status == 400:
            kind = "fatal"                                   # malformed request = code bug; same every time
        else:
            kind = "retryable"
        m = re.search(r"retryDelay['\"]?:\s*['\"](\d+)s", text)
        return LLMResult(error=friendly_api_error(status or 0, text), error_kind=kind, settings=settings,
                         retry_after_s=float(m.group(1)) if m else None)

    um = resp.usage_metadata
    parsed, perr = _parse_json(resp.text)
    return LLMResult(parsed=parsed, raw_text=resp.text, model_version=resp.model_version,
                     prompt_tokens=getattr(um, "prompt_token_count", None),
                     output_tokens=getattr(um, "candidates_token_count", None),
                     thought_tokens=getattr(um, "thoughts_token_count", None),
                     error=perr, error_kind="bad_output" if perr else None, settings=settings)


def _status_from_text(text: str):
    m = re.match(r"\s*(\d{3})\b", text)
    return int(m.group(1)) if m else None


# =====================================================================
#  OpenAI (official Responses API; ready, waiting for an API key and model name in config)
# =====================================================================
OPENAI_URL = "https://api.openai.com/v1/responses"


def openai_schema(node):
    """Same schema in OpenAI's strict form: lowercase types and additionalProperties false. Wording is unchanged."""
    if isinstance(node, list):
        return [openai_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k == "type" and isinstance(v, str):
            out[k] = v.lower()
        elif k == "properties":
            out[k] = {name: openai_schema(prop) for name, prop in v.items()}
        else:
            out[k] = openai_schema(v)
    if out.get("type") == "object":
        out["additionalProperties"] = False
    return out


def openai_body(cfg, system_prompt, user_prompt, schema, condition) -> dict:
    body = {"model": cfg["model_name"], "instructions": system_prompt, "input": user_prompt, "store": False,
            "text": {"format": {"type": "json_schema", "name": "answer", "strict": True,
                                "schema": openai_schema(schema)}}}
    effort = cfg["conditions"][condition].get("reasoning_effort")
    if effort:
        body["reasoning"] = {"effort": effort}
    if cfg.get("send_temperature", True):
        body["temperature"] = cfg["temperature"]
    return body


def _openai(cfg, system_prompt, user_prompt, schema, condition) -> LLMResult:
    import requests
    if not cfg["model_name"]:
        return LLMResult(error="OpenAI model name not set in config.V2_LLM_MODELS['openai_main']", error_kind="fatal")
    body = openai_body(cfg, system_prompt, user_prompt, schema, condition)
    settings = {k: body[k] for k in ("model", "temperature", "reasoning") if k in body}
    headers = {"Authorization": f"Bearer {load_env_key(cfg['api_key_env'])}", "Content-Type": "application/json"}
    try:
        r = requests.post(OPENAI_URL, headers=headers, json=body, timeout=300)
    except requests.RequestException as e:
        return LLMResult(error=f"network error: {type(e).__name__}", error_kind="retryable", settings=settings)
    if r.status_code != 200:
        kind = "fatal" if is_fatal_error(r.status_code, r.text) or r.status_code == 400 else "retryable"
        return LLMResult(error=friendly_api_error(r.status_code, r.text), error_kind=kind, settings=settings)
    data = r.json()
    if data.get("status") not in (None, "completed"):
        return LLMResult(error=f"incomplete answer: {data.get('incomplete_details')}", error_kind="bad_output",
                         settings=settings)
    text = "".join(c.get("text", "") for item in data.get("output", []) if item.get("type") == "message"
                   for c in item.get("content", []) if c.get("type") == "output_text")
    parsed, perr = _parse_json(text)
    um = data.get("usage") or {}
    return LLMResult(parsed=parsed, raw_text=text, model_version=data.get("model"),
                     prompt_tokens=um.get("input_tokens"), output_tokens=um.get("output_tokens"),
                     thought_tokens=(um.get("output_tokens_details") or {}).get("reasoning_tokens"),
                     error=perr, error_kind="bad_output" if perr else None, settings=settings)


# =====================================================================
#  Mock (offline tests only — deterministic, with injected failures)
# =====================================================================
_mock_calls = itertools.count()


def _mock(cfg, system_prompt, user_prompt, schema, condition) -> LLMResult:
    h = stable_hash(user_prompt, condition, next(_mock_calls))        # independent per call
    if cfg.get("fail_rate") and (h % 1000) / 1000 < cfg["fail_rate"]:
        return LLMResult(error="mock injected 503 UNAVAILABLE", error_kind="retryable",
                         settings={"model": cfg["model_name"]})
    base = stable_hash(user_prompt) % 1000 / 1000
    props = schema.get("properties", {})
    if "latitude" in props:                                  # grounding schema
        parsed = {"locality": "Mock Nagar", "latitude": 12.95 + base * 0.1, "longitude": 77.55 + base * 0.1,
                  "confidence": "medium"}
    else:                                                    # benchmark schema
        slot_mult = 1.8 if "Rush" in user_prompt else (1.0 if "Night" in user_prompt else 1.3)
        dist = round(3 + base * 18, 1)
        roads = ["Mock Main Road", "Outer Ring Road"]
        minutes = round(dist * 2.2 * slot_mult)
        by_road = props.get("suggested_route", {}).get("items", {}).get("type") == "OBJECT"
        parsed = {"suggested_route": [{"road_name": n, "distance_km": dist / 2, "time_minutes": minutes / 2}
                                      for n in roads] if by_road else roads,
                  "estimated_distance_km": dist,
                  "estimated_time_minutes": minutes,
                  "traffic_awareness": "heavy" if slot_mult > 1.5 else ("light" if slot_mult == 1.0 else "moderate"),
                  "reasoning": "mock answer for pipeline testing"}
    text = json.dumps(parsed)
    return LLMResult(parsed=parsed, raw_text=text, model_version="mock-1", prompt_tokens=len(user_prompt) // 4,
                     output_tokens=len(text) // 4, thought_tokens=0 if condition == "A" else 1200,
                     settings={"model": cfg["model_name"], "temperature": cfg["temperature"]})


# =====================================================================
#  Placeholders for later providers (keep the same contract)
# =====================================================================
def _not_implemented(name):
    def adapter(cfg, *a, **k):
        return LLMResult(error=f"{name} adapter not implemented yet: add it in llm_clients.py "
                               f"(same inputs, return LLMResult with JSON parsed against the schema)",
                         error_kind="fatal")
    return adapter


_ADAPTERS = {
    "gemini": _gemini,
    "mock": _mock,
    "openai": _openai,
}
