# API keys and billing

Keys live only in `.env` at the project root (git-ignored; template: `.env.example`). Scripts never print them.

| Variable | Used for | Where to get it |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | Geocoding, Places (landmarks), Routes (traffic scrape, benchmark ground truth) | Google Cloud Console → APIs & Services → Credentials |
| `GEMINI_API_KEY` | Gemini benchmark queries | Google AI Studio → Get API key |
| `CHATGPT_API_KEY` | ChatGPT benchmark queries (OpenAI Responses API) | platform.openai.com → API keys |

## Setup
1. **Google Maps:** enable `Routes API`, `Places API (New)` and `Geocoding API` in the key's project, link a billing
   account, and restrict the key to these three APIs. Monthly free usage applies per SKU (Routes Pro 5,000,
   Places Text Search Pro 5,000, Geocoding 10,000 at the time of writing).
2. **Gemini:** the key's project needs billing (paid tier). On the free tier the model allows about 20 requests a day
   and requests are refused first when the model is busy.
3. **OpenAI:** API usage is billed separately from ChatGPT subscriptions; the account needs prepaid credit.
4. **Safety:** set a budget alert and a daily request quota in the Cloud Console; for prepaid credit keep auto-reload off.
5. **Before any full run:** use `--dry-run` (count, cost, sample request, no network) and `--limit 1` (one real call).

## Errors
Failed calls are stored with the error and retried on the next run; they never count as completed.

| Error | Meaning | Fix |
|---|---|---|
| `403 PERMISSION_DENIED` / `BILLING_DISABLED` | API not enabled, or no active billing | Enable the API; link or reactivate billing |
| `REQUEST_DENIED` / key not authorized | Key restriction blocks the API | Add the API to the key's allowed list |
| `400 API_KEY_INVALID` | Wrong key in `.env` | Copy the key again |
| `429 RESOURCE_EXHAUSTED` | Rate or daily quota reached (free tier) | Enable billing or wait; reruns resume |
| `429 insufficient_quota` (OpenAI) | No API credit | Add credit |
| `404` model not found | Model unavailable to this key | Change `model_name` in `config.py` (`V2_LLM_MODELS`) |
| `400 INVALID_ARGUMENT` | Malformed request | Check schema and parameters |
| `503` / `504` | Model temporarily overloaded | Automatic retry with back-off (120 s timeout per request) |
