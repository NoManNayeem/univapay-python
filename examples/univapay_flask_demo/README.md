# Univapay Flask Demo (Full-Stack)

A minimal full-stack example showing how to integrate the **Univapay-Python SDK** with Flask, a SQLite database, and a simple front-end.

## Features

- One-time charge (server-side finalize with `ChargesAPI`)
- Subscription create (with `SubscriptionsAPI`)
- Recurring token flow (server-side uses the same `ChargesAPI`)
- Refund & Cancel actions
- Dev webhook endpoint (stores raw events)
- SQLite storage for products, charges, subscriptions, refunds & events

> ⚠️ This is a demo. Review and harden before production (signature verification, auth, CSRF, proper error handling, etc.).

## Setup

From the repo root, ensure the SDK is installed (editable is recommended):

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dotenv]"
```

Then install the demo app requirements and configure env:

```bash
cd examples/univapay_flask_demo
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your UNIVAPAY_* values
```

Run the app:

```bash
python app.py
# or FLASK_DEBUG=1 python app.py
# Open http://127.0.0.1:5001/
```

## How it works

- `GET /api/widget-config` builds a widget envelope using your `UNIVAPAY_JWT` (client token).
- Front-end (static/app.js) simulates widget behavior: it prompts you for a `tokenId` then calls:
  - `POST /api/charges` for one-time/recurring
  - `POST /api/subscriptions` for subscription
- Server finalizes with Univapay using the SDK and stores the results in `app.sqlite3`.
- `GET /admin` shows recent records and lets you refund or cancel charges.
- Dev webhook at `POST /webhook/univapay` simply stores raw events (add signature verification for real use).

## Toggle payment "gateways"

The UI includes checkboxes whose values are passed through to the widget config under a JSON field named `gateways`. Adapt these keys to actual widget configuration options for your account. Unknown keys are ignored by the widget.

## Notes

- For production, implement CSRF protection, authentication, robust input validation, and webhook signature verification (see `univapay.resources.webhooks`).

Enjoy!
