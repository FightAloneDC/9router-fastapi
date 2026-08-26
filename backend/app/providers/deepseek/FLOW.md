# DeepSeek Provider Flow

`https://api.deepseek.com` — OpenAI-compatible chat. New API
accounts receive a **~5M token signup grant** valid **~30 days**
from registration (no credit card). After that, billing is
pay-as-you-go from topped-up balance.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS` |
| `models.py` | `/models` list parsing |
| `quota.py` | `GET /user/balance` + local token bar |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID          = deepseek
ALIAS                = ds
BASE_URL             = https://api.deepseek.com
FORMAT               = openai
MODEL_CATALOG_TABLE  = True
AUTH                 = Bearer apiKey
CATEGORY             = freeTier
```

`RATE_LIMITS`:

| Key | Meaning |
|-----|---------|
| `signup_grant` | 5M tokens, 30 days, ~$8.40 marketed value |
| `deepseek-v4-pro` | 500 concurrent requests |
| `deepseek-v4-flash` | 2500 concurrent requests |
| `deepseek-v4-flash-vision-exp` | 2500 concurrent requests |

No fixed RPM/TPM table in official docs — dynamic throttling
under load; 429 when concurrency exceeded.

Sources (retrieved 2026-08-26):

- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/quick_start/rate_limit
- https://api-docs.deepseek.com/api/get-user-balance

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="ds/deepseek-v4-flash"
  → alias ds → provider deepseek
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → usage_history as usual
```

Default handler — no custom `handler.py`.

## Models

Catalog rows in `provider_models` (`MODEL_CATALOG_TABLE`). Fetch
from `GET /models`. Upstream model ids (2026-08):

- `deepseek-v4-flash` (V4-Flash-0731)
- `deepseek-v4-pro` (V4-Pro-0813)
- `deepseek-v4-flash-vision-exp`

Legacy ids (`deepseek-chat`, `deepseek-reasoner`) may still
appear from older keys — enable only what `/models` returns.

## Quota (`quota.py`)

### Upstream balance

`GET /user/balance` with Bearer apiKey:

```json
{
  "is_available": true,
  "balance_infos": [{
    "currency": "USD",
    "total_balance": "8.40",
    "granted_balance": "6.12",
    "topped_up_balance": "0.00"
  }]
}
```

Bars:

1. **Signup grant tokens** (free) — local `usage_history` sum vs
   5M; `reset_at` = grant expiry.
2. **API balance (USD)** (free) — `total_balance` from
   `/user/balance` (prepaid remaining, e.g. `$3.15 left`).
3. **Granted / API balance** (payg/subscribe) — detailed USD bars.

`plan` on the quota card mirrors connection `accountType`
(`free` / `payg` / `subscribe`), not the balance API shape.

`limit_reached` when `is_available` is false, grant window
expired, or free tokens + granted USD are both exhausted.

`USES_UPSTREAM = False` — quota list refreshes on each load
(local token sum + balance poll).

## UI

- Provider Detail: `rateLimits` table (grant + concurrency).
- Quota Tracker: balance + local token bars.
- Notice: signup grant summary on `/providers/deepseek`.
