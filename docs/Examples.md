# Examples

This repository includes small runnable scripts and a Flask demo app to help you test common flows quickly.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
python -m pip install -U pip
python -m pip install -e ".[dotenv]"

# Export env or create .env at project root
export UNIVAPAY_JWT=...
export UNIVAPAY_SECRET=...
export UNIVAPAY_STORE_ID=...
```

## Scripts

- `examples/charge_one_time.py`: create a one-time charge
- `examples/charge_recurring.py`: create a charge with a recurring token
- `examples/charge_capture.py`: capture a previously authorized charge
- `examples/charge_cancel.py`: cancel/void a charge
- `examples/refund_create.py`: create a refund (full or partial)
- `examples/refund_list.py`: list refunds for a charge
- `examples/subscription_create.py`: create a subscription
- `examples/subscription_get.py`: get a subscription
- `examples/subscription_cancel.py`: cancel a subscription
- `examples/token_check.py`: fetch a transaction token by id
- `examples/smoke_api.py`: quick connectivity check for API
- `examples/smoke_widget.py`: show widget payloads on stdout
- `examples/webhook_verify_sample.py`: verify a webhook signature from sample data

Each script supports basic CLI args (see `examples/_common.py`).

## Flask Demo

Path: `examples/univapay_flask_demo/`

- `app.py`: minimal backend with routes to render widget pages and handle server-side calls (charges/subscriptions)
- `.env.example`: sample env settings; copy to `.env` and fill values
- `static/` and `templates/`: example frontend pages using the official widget

Run:

```bash
cd examples/univapay_flask_demo
python -m pip install -r requirements.txt
cp .env.example .env  # then edit
flask --app app run --debug
```

Open http://127.0.0.1:5000 to try the demo.

