# Univapay-Python (Unofficial)

Framework-agnostic Python SDK for Univapay integrations.

- Build frontend widget configs (one-time, subscription, recurring)
- Server-side APIs for Charges, Subscriptions, Refunds/Cancels, and Token reads
- Webhook verification and a tiny event router
- Utilities: currency minor units, idempotency keys, metadata sanitization
- Clean debug logs and unified HTTP errors

Status: Alpha. This is an independent SDK built for rapid integration/testing - not an official Univapay package. Please verify routes/fields against your account's API docs and adjust as needed.

---

## Installation

```bash
# (Recommended) use a virtualenv
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# Editable install (with optional dotenv support)
python -m pip install -U pip
python -m pip install -e ".[dotenv]"
```

Test the import:

```bash
python - <<'PY'
import univapay
print("SDK version:", univapay.__version__)
PY
```

Supported Python: 3.9-3.12

---

## Configuration

Server-side API calls require both `UNIVAPAY_JWT` and `UNIVAPAY_SECRET`.

You can provide values via environment variables or explicitly in `UnivapayConfig`.

Environment variables:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `UNIVAPAY_JWT` | yes | - | FE App Token (JWT) used by the widget and server auth (with secret) |
| `UNIVAPAY_SECRET` | yes | - | Server secret - keep safe |
| `UNIVAPAY_STORE_ID` | often | - | Required for most store-scoped calls |
| `UNIVAPAY_BASE_URL` | no | `https://api.univapay.com` | Override for sandbox/alt envs |
| `UNIVAPAY_TIMEOUT` | no | `30` seconds | HTTP timeout |
| `UNIVAPAY_DEBUG` | no | `1` | Set `0/false/no/off` to disable SDK logs |
| `UNIVAPAY_WIDGET_URL` | no | official loader URL | Optional override for widget loader |

You may also add a local `.env` file if you installed with the `dotenv` extra. See docs/Configuration.md for details.

---

## Quick start (server)

```python
from univapay import UnivapayConfig, UnivapayClient
from univapay.resources import ChargesAPI
from univapay.utils import make_idempotency_key

cfg = UnivapayConfig().validate()  # pulls from env/.env

with UnivapayClient(cfg, retries=1, backoff_factor=0.5) as client:
    charges = ChargesAPI(client)
    charge = charges.create_one_time(
        token_id="transaction_token_from_widget",
        amount=12000,                 # minor units (e.g., 12000 JPY)
        currency="jpy",
        capture=True,
        idempotency_key=make_idempotency_key("one_time"),
    )
    print("charge id:", charge.id)
```

Auth header format: `Authorization: Bearer {secret}.{jwt}`.

All HTTP failures raise `UnivapayHTTPError(status, payload, request_id)`.

---

## Widgets (frontend payloads)

Build FE-safe JSON payloads your frontend passes to the official Univapay widget.

```python
from univapay.widgets import (
    build_one_time_widget_config,
    build_subscription_widget_config,
    build_recurring_widget_config,
    widget_loader_src,
    to_json,
)

# One-time
one_time_cfg = build_one_time_widget_config(
    amount=12000,
    form_id="form-one-time",
    button_id="btn-one-time",
    description="Product A - One-time",
)

# Subscription
sub_cfg = build_subscription_widget_config(
    amount=59400,
    period="semiannually",
    form_id="form-sub",
    button_id="btn-sub",
    description="Six-month Plan",
)

# Recurring (merchant-initiated tokenized charges)
rec_cfg = build_recurring_widget_config(
    amount=30000,
    form_id="form-recurring",
    button_id="btn-recurring",
    description="Recurring Billing",
)

print(to_json(one_time_cfg, pretty=True))
print(widget_loader_src())  # loader URL (env-driven override supported)
```

Payment method toggles: pass `payment_methods` to builders (the SDK filters known keys), or pass additional widget options via `**extra` (merged verbatim). See docs/Widgets.md for details and FE event hooks.

---

## Server APIs

Charges:

```python
from univapay.resources import ChargesAPI

charges = ChargesAPI(client)
ch = charges.create_one_time(token_id="...", amount=12000, currency="jpy", capture=True)
final = charges.wait_until_terminal(ch.id, server_polling=True)
refund = charges.refund(ch.id, amount=6000)
cap = charges.capture(ch.id)
cnl = charges.cancel(ch.id)
```

Subscriptions:

```python
from univapay.resources import SubscriptionsAPI

subs = SubscriptionsAPI(client)
s = subs.create(token_id="subscription_token", amount=59400, period="semiannually", currency="jpy")
s_done = subs.wait_until_terminal(s.id, server_polling=False, timeout_s=60, interval_s=2)
subs.cancel(s.id)
```

Refunds:

```python
from univapay.resources import RefundsAPI

refunds = RefundsAPI(client)
r = refunds.create(charge_id="...", amount=1200, reason="customer request")
r2 = refunds.get(charge_id="...", refund_id=r.id)
```

Tokens:

```python
from univapay.resources import TokensAPI

tokens = TokensAPI(client)
t = tokens.get("transaction_token_id")
print(t.id, t.token_type, t.status)
```

---

## Webhooks

```python
from univapay.resources import parse_event, WebhookVerificationError

try:
    ev = parse_event(
        body=request_body_bytes,
        headers=request_headers,
        secret=WEBHOOK_SECRET,
        tolerance_s=300,
    )
    print(ev.type)
except WebhookVerificationError as e:
    print("invalid signature:", str(e))
```

See docs/Webhooks.md and the Flask demo for framework-ready snippets.

---

## Utilities

```python
from decimal import Decimal
from univapay.utils import (
    to_minor_units, from_minor_units,
    normalize_currency, currency_exponent,
    make_idempotency_key, ensure_idempotency_key,
    uuid_str, utcnow_iso, safe_metadata,
)

to_minor_units(Decimal("12.34"), "usd")   # -> 1234
from_minor_units(59400, "jpy")            # -> Decimal('59400')
normalize_currency("JPY")                 # -> "jpy"
currency_exponent("usd")                  # -> 2
make_idempotency_key("charge")            # -> "charge_<uuid>"
safe_metadata({"order": 123, "price": Decimal("12.34")})
```

---

## Examples and Demo

- Scripts: see the `examples/` folder (charges, subscriptions, refunds, tokens, widget payloads, webhook verify).
- Flask demo:  `examples/univapay_flask_demo/` - minimal end-to-end app with templates and routes. 

Refer to docs/Examples.md for commands.

---

## Documentation

This repo ships with an MkDocs site (Material + mkdocstrings).

Build locally:

```bash
pip install mkdocs mkdocs-material "mkdocstrings[python]"
mkdocs serve
```

Key pages:

- Quickstart: docs/Quickstart.md
- Configuration: docs/Configuration.md
- Widgets: docs/Widgets.md
- Webhooks: docs/Webhooks.md
- Examples: docs/Examples.md
- API Reference: docs/API.md

---

## Contributing

PRs and issues welcome!

- Repo: https://github.com/NoManNayeem/Univapay-Python

---

## License

MIT
