# Univapay-Python (Unofficial)

Framework-agnostic Python helpers for Univapay integrations:

- Build frontend widget configs (one-time, subscription, recurring)
- Server-side APIs for Charges, Subscriptions, Refunds/Cancels, and Token reads
- Webhook verification & tiny event router
- Handy utils (currency minor units, idempotency keys, metadata sanitization)
- Clean debug logs and unified HTTP errors

Status: Alpha. This is an independent SDK built for rapid integration/testing — not an official Univapay package. Please verify routes/fields against your account's API docs and update as needed.

---

## Installation

```bash
# (Recommended) use a virtualenv
python -m venv .venv
source .venv/bin/activate           # on Windows: .venv\Scripts\activate

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

Supported Python: 3.9–3.12

---

## Configuration

Server-side API calls require both UNIVAPAY_JWT and UNIVAPAY_SECRET.

You can provide values via environment variables or explicitly in `UnivapayConfig`.

### Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `UNIVAPAY_JWT` | yes | — | FE App Token (JWT) used by the widget and server auth (combined with secret) |
| `UNIVAPAY_SECRET` | yes | — | Server secret — keep safe |
| `UNIVAPAY_STORE_ID` | often | — | Required for most store-scoped calls |
| `UNIVAPAY_BASE_URL` | no | `https://api.univapay.com` | Change for sandbox/alt envs |
| `UNIVAPAY_TIMEOUT` | no | `30` seconds | HTTP timeout |
| `UNIVAPAY_DEBUG` | no | `1` (on) | Set `0/false/no/off` to disable SDK logs |
| `UNIVAPAY_WIDGET_URL` | no | official loader URL | Optional override for widget loader |

You may also add a local `.env` file if you installed with the `dotenv` extra.

---

## Quick start (Server)

```python
from univapay import UnivapayConfig, UnivapayClient
from univapay.resources import ChargesAPI, SubscriptionsAPI, RefundsAPI, CancelsAPI, TokensAPI
from univapay.utils import make_idempotency_key

cfg = UnivapayConfig().validate()  # pulls from env/.env

with UnivapayClient(cfg, retries=1, backoff_factor=0.5) as client:
    charges = ChargesAPI(client)
    subs    = SubscriptionsAPI(client)
    refunds = RefundsAPI(client)
    cancels = CancelsAPI(client)
    tokens  = TokensAPI(client)

    # Example: create a one-time charge
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

Unified error handling: all HTTP failures raise `UnivapayHTTPError(status, payload, request_id)`.

---

## Frontend widget configs

Server builds FE-safe JSON payloads your frontend passes to the official Univapay widget.

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
    period="semiannually",  # daily|weekly|biweekly|monthly|bimonthly|quarterly|semiannually|annually
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

# Loader URL (env-driven override supported)
print(widget_loader_src())
```

Payment method toggles: pass `payment_methods` to builders (SDK filters known keys), or pass additional widget options via `**extra` (merged verbatim).

### Direct JS usage (checkbox-driven paymentMethods)

```html
<script src="https://widget.univapay.com/client/checkout.js"></script>

<form id="payment-form">
  <button id="univapay-payment-checkout">Pay</button>
 </form>

<script>
  var checkout = UnivapayCheckout.create({
    appId: "<APP_JWT>",
    checkout: "payment",
    amount: 1000,
    currency: "jpy",
    cvvAuthorize: true,
    paymentMethods: [
      "card","bank_transfer","alipay_online","pay_pay_online","we_chat_online","d_barai_online","alipay_plus_online"
    ],
    onSuccess: function () { document.getElementById('payment-form').submit(); }
  });
  document.getElementById('univapay-payment-checkout').onclick = function () { checkout.open(); };
</script>
```

### Frontend event hooks (example)

```html
<script>
window.addEventListener("univapay:opened", (e) => console.log("[event] opened", e));
window.addEventListener("univapay:closed", (e) => console.log("[event] closed", e));
window.addEventListener("univapay:success", (e) => {
  // Often includes tokenId, and may include chargeId / subscriptionId
  console.log("[event] success", e.detail);
});
</script>
```

---

## Charges API

```python
from univapay.resources import ChargesAPI

charges = ChargesAPI(client)

# One-time
ch = charges.create_one_time(token_id="...", amount=12000, currency="jpy", capture=True)

# Recurring (token from a 'recurring' widget)
ch2 = charges.create_recurring(token_id="...", amount=30000, currency="jpy")

# Get / wait
ch3 = charges.get(ch.id)
final = charges.wait_until_terminal(ch.id, server_polling=True)  # or client-side polling

# Refunds (also see RefundsAPI for list/get)
refund = charges.refund(ch.id, amount=6000)

# Optional capture/cancel endpoints (if your account uses auth/capture)
cap = charges.capture(ch.id)
cnl = charges.cancel(ch.id)
```

Terminal states include: `successful`, `failed`, `error`, `canceled`.

---

## Subscriptions API

```python
from univapay.resources import SubscriptionsAPI

subs = SubscriptionsAPI(client)

# Create
s = subs.create(
    token_id="subscription_token_from_widget",
    amount=59400,
    period="semiannually",
    currency="jpy",
)

# Read / wait
s_now = subs.get(s.id)
s_done = subs.wait_until_terminal(s.id, server_polling=False, timeout_s=60, interval_s=2)

# Cancel
subs.cancel(s.id)
```

The SDK treats several values as "terminal-ish" (case-insensitive), including `current`, `active`, `canceled/cancelled`, `failed`, `paused`, etc., to match values seen across environments.

---

## Refunds API

```python
from univapay.resources import RefundsAPI

refunds = RefundsAPI(client)

# Create (full if amount omitted and account allows)
r = refunds.create(charge_id="...", amount=1200, reason="customer request")

# Read
r2 = refunds.get(charge_id="...", refund_id=r.id)

# List
page = refunds.list(charge_id="...", limit=20)
```

---

## Tokens API

```python
from univapay.resources import TokensAPI

tokens = TokensAPI(client)
t = tokens.get("transaction_token_id")
print(t.id, t.token_type, t.status)
```

---

## Webhooks

Includes signature verification (timestamped, sha256, raw hex) and a permissive event model.

```python
# app.py (Flask example)
from flask import Flask, request, jsonify
from univapay.resources import parse_event, WebhookRouter, WebhookVerificationError

app = Flask(__name__)

WEBHOOK_SECRET = "your_webhook_secret"  # keep safe

router = WebhookRouter()

@router.on("*")
def _all(ev):
    print("[Webhook] type:", ev.type, "resource:", ev.resource_type)

@app.post("/webhook/univapay")
def webhook():
    try:
        ev = parse_event(
            body=request.get_data(cache=False, as_text=False),
            headers=request.headers,
            secret=WEBHOOK_SECRET,
            # header_name="X-Univapay-Signature",  # optionally force a name
            tolerance_s=300,
            skip_verification=False,              # set True only in local dev
        )
        results = router.dispatch(ev)
        return jsonify({"ok": True, "handled": len(results)})
    except WebhookVerificationError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
```

The parser keeps unknown fields and returns the full raw payload in `event.data`.

---

## Flask demo (optional)

The included Flask demo provides:

- Customer view (/customer): product grid, checkbox-driven payment method selection, recent activity tables
- Admin view (/admin): charges/subscriptions/refunds with actions (refund/cancel/refresh), export JSON, pagination
- Settings page (/settings): edit UNIVAPAY_* secrets in UI (stored locally in SQLite)
- RBAC: role switcher in topbar (customer/merchant); admin routes require merchant

Run it:

```bash
python examples/univapay_flask_demo/app.py
# Visit http://127.0.0.1:5001
```

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

## Debugging & errors

- Toggle SDK logs with `UNIVAPAY_DEBUG=1|0` (default on during development).
- HTTP failures raise `UnivapayHTTPError`. Attributes:
  - `status` (int) — HTTP status (or `-1` for network errors)
  - `payload` (Any) — parsed JSON or text fallback
  - `request_id` (str|None) — server-provided correlation id if available
- Successful responses include rate-limit hints (when available) under `['_meta']['rate_limits']`.

---

## Examples

See the `examples/` folder for small scripts (create charges, subscriptions, refunds, etc.).

---

## Contributing

PRs and issues welcome!

- Repo: <https://github.com/NoManNayeem/Univapay-Python>
- Author: Nayeem Islam — <islam.nayeem@outlook.com>

---

## License

MIT
