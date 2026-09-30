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
            _gemini_clients[cfg["api_key_env"]] = genai.Client(api_key=load_env_key(cfg["api_key_env"]))
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
        parsed = {"suggested_route": ["Mock Main Road", "Outer Ring Road"],
                  "estimated_distance_km": dist,
                  "estimated_time_minutes": round(dist * 2.2 * slot_mult),
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
    "openai": _not_implemented("OpenAI"),
    "anthropic": _not_implemented("Anthropic"),
}
