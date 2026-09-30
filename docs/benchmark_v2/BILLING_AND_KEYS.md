# API keys, billing, quotas — step by step

Keys live only in `.env` (git-ignored): `GOOGLE_MAPS_API_KEY`, `GEMINI_API_KEY`. Scripts never print keys.
Cost estimates for the project: see the plan's cost table (≈ $8 without condition B, ≈ $35–70 with B; prices checked 2026-09-30).

## A. Gemini API key (Google AI Studio)
1. Open https://aistudio.google.com → left menu **Get API key**. Find the key that is in `.env` (compare the last 4 characters) and note its **Google Cloud project** name.
2. Enable billing for that project — either:
   - on the key's row click **Set up billing** and follow the prompts, or
   - https://console.cloud.google.com → top bar select that project → **Billing** → **Link a billing account** → create one (add a card).
   Indian cards: the bank may ask for an e-mandate / OTP; approve it. A small verification charge may appear and be refunded.
3. Verify: AI Studio → **Usage & tier** (or the key row) shows **Tier 1** (paid). Per-minute limits rise; the ~20 requests/day free cap disappears.
4. Safety cap:
   - **Alert** (does not stop spend): Cloud Console → Billing → **Budgets & alerts** → Create budget → scope: this project → amount e.g. ₹1,000 → thresholds 50 %, 90 %, 100 % → email.
   - **Hard cap**: Cloud Console → **APIs & Services → Enabled APIs → Generative Language API → Quotas & system limits** → edit "Requests per day" (e.g. 3,000). Requests beyond it fail with 429 and the script resumes later.
5. Test: Claude runs one call with `--limit 1` (after you approve) and shows you the result.

## A2. Our situation (checked by Ishan in AI Studio, 2026-10-01)
| Project | Keys | Billing tier | Status |
|---|---|---|---|
| Default Gemini Project (`gen-lang-client-0190754255`) | 2 (the key currently in `.env`) | **Free tier** | — |
| My First Project (`project-616e4e16-…`) | 1 | Tier 1 · Postpay | **"Prepay required"** |
"Prepay required" = Google wants prepaid Gemini credit loaded before this project can make paid calls (appears for some
newer accounts). **Recommended:** use *My First Project* → **Set up prepay** → load **≈ ₹1,000** first (covers tests,
grounding, condition A for both models ≈ $6, with margin; GST may be added) → top up ≈ ₹2,000 before condition B.
Prepaid credit is itself a **hard spending cap**. Then copy that project's key into `.env` as `GEMINI_API_KEY`
(Ishan does this; keys are never pasted in chat) → Claude verifies with 1 test call.
Optional second net: budget alert ≈ ₹3,000 on the billing account.

## B. Google Maps key (Places API (New), Routes API, Geocoding API)
1. Cloud Console → select the key's project → **APIs & Services → Library** → search and **Enable**: `Places API (New)`, `Routes API`, `Geocoding API`.
2. **Billing** must be linked (same as A2). Monthly free usage per SKU applies automatically (Routes Pro 5,000/month, Places Text Search Pro 5,000/month, Geocoding 10,000/month — shared across all projects on the billing account).
3. **Credentials** → click the key → *API restrictions* → *Restrict key* → tick only the three APIs above. (Keep the Gemini key separate.)
4. **Hard cap**: APIs & Services → Routes API → **Quotas** → "Compute routes requests per day" e.g. 2,500; Places API (New) → Text Search per day e.g. 300.
5. Budget alert as in A4.

## C. Error → meaning → fix
Scripts translate these into plain messages; failed calls are logged with the error and are **never** counted as completed.

| Error seen | Meaning | Fix |
|---|---|---|
| `403 PERMISSION_DENIED` "… API has not been used in project … or it is disabled" | API not enabled | B1 |
| `403` "… requires billing to be enabled" / `BILLING_DISABLED` | No billing account linked | A2 / B2 |
| `REQUEST_DENIED` / "This API key is not authorized to use this service" | Key restriction blocks the API | B3 (add the API to the allowed list) |
| `400 API_KEY_INVALID` | Wrong/typo key in `.env` | Copy the key again into `.env` |
| `429 RESOURCE_EXHAUSTED` | Rate or daily quota reached (free tier ≈ 20/day for Gemini) | Enable billing (A2) or wait; resume is automatic |
| `404 NOT_FOUND` model … | Model name unavailable to this key | Change `model_name` in `config.py` `V2_LLM_MODELS` |
| `400 INVALID_ARGUMENT` | Bad request (schema, parameter) | Code bug — Claude fixes it |
| `503 UNAVAILABLE` | Temporary server overload | Automatic retry with back-off |

If you hit anything else: copy the exact error line (it never contains the key) and send it to Claude.
