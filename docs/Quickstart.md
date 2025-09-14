# Quickstart

This guide gets you from zero to a working server-side integration using the Univapay-Python SDK.

## 1) Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e ".[dotenv]"
```

## 2) Configure

Set the following environment variables (or use a `.env` file):

-  `UNIVAPAY_JWT` - App Token (JWT) 
-  `UNIVAPAY_SECRET` - Server secret 
-  `UNIVAPAY_STORE_ID` - Your store id (often required) 

Optional:

- `UNIVAPAY_BASE_URL` (default `https://api.univapay.com`)
- `UNIVAPAY_TIMEOUT` (default 30)
- `UNIVAPAY_DEBUG` (default 1)

## 3) Make a simple charge

```python
from univapay import UnivapayConfig, UnivapayClient
from univapay.resources import ChargesAPI
from univapay.utils import make_idempotency_key

cfg = UnivapayConfig().validate()
with UnivapayClient(cfg, retries=1, backoff_factor=0.5) as client:
    charges = ChargesAPI(client)
    charge = charges.create_one_time(
        token_id="token_from_widget",
        amount=12000,  # minor units
        currency="jpy",
        capture=True,
        idempotency_key=make_idempotency_key("quickstart"),
    )
    print("charge:", charge.id, charge.status)
```

## 4) Webhook verification

```python
from flask import Flask, request, jsonify
from univapay.resources import parse_event, WebhookVerificationError

app = Flask(__name__)
WEBHOOK_SECRET = "your_webhook_secret"

@app.post("/webhook/univapay")
def webhook():
    try:
        ev = parse_event(
            body=request.get_data(cache=False, as_text=False),
            headers=request.headers,
            secret=WEBHOOK_SECRET,
            tolerance_s=300,
            skip_verification=False,
        )
        return jsonify({"ok": True, "type": ev.type})
    except WebhookVerificationError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
```

## 5) Frontend widget config

```python
from univapay.widgets import build_one_time_widget_config, to_json

payload = build_one_time_widget_config(
    amount=12000,
    form_id="form-one-time",
    button_id="btn-one-time",
    description="Product A - One-time",
)
print(to_json(payload, pretty=True))
```

Next: see [Using with Python](Using-with-Python.md) for common flows and [API Reference](API.md) for details.

