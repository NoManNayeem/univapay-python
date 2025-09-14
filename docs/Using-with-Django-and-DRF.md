# Using with Django & DRF

This guide shows how to integrate the Univapay-Python SDK with a typical Django + DRF stack.

## Install

```bash
pip install djangorestframework
pip install -e ".[dotenv]"
```

## Settings

Set environment variables (or use `python-dotenv` in `manage.py`/`wsgi.py`):

```env
UNIVAPAY_JWT=...
UNIVAPAY_SECRET=...
UNIVAPAY_STORE_ID=...
UNIVAPAY_BASE_URL=https://api.univapay.com
```

## Client dependency

```python
# app/univapay_client.py
from univapay import UnivapayConfig, UnivapayClient

def get_client() -> UnivapayClient:
    cfg = UnivapayConfig().validate()
    return UnivapayClient(cfg, retries=1, backoff_factor=0.5)
```

## DRF views

```python
# app/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from univapay.resources import ChargesAPI, SubscriptionsAPI
from .univapay_client import get_client

@api_view(["POST"])
def create_charge(request):
    token_id = request.data.get("tokenId")
    amount = int(request.data.get("amount", 0))
    currency = request.data.get("currency", "jpy")
    if not token_id or amount <= 0:
        return Response({"error": "tokenId and amount required"}, status=status.HTTP_400_BAD_REQUEST)

    client = get_client()
    try:
        with client as c:
            charges = ChargesAPI(c)
            ch = charges.create_one_time(token_id=token_id, amount=amount, currency=currency)
            return Response(ch.model_dump())
    finally:
        client.close()

@api_view(["POST"])
def create_subscription(request):
    token_id = request.data.get("tokenId")
    amount = int(request.data.get("amount", 0))
    currency = request.data.get("currency", "jpy")
    period = request.data.get("period")
    if not token_id or amount <= 0 or not period:
        return Response({"error": "tokenId, amount, period required"}, status=status.HTTP_400_BAD_REQUEST)

    client = get_client()
    try:
        with client as c:
            subs = SubscriptionsAPI(c)
            s = subs.create(token_id=token_id, amount=amount, period=period, currency=currency)
            return Response(s.model_dump())
    finally:
        client.close()
```

## Webhook view

```python
# app/webhooks.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from univapay.resources import parse_event, WebhookVerificationError
import os

WEBHOOK_SECRET = os.getenv("UNIVAPAY_WEBHOOK_SECRET")

@api_view(["POST"])
def univapay_webhook(request):
    try:
        ev = parse_event(body=request.body, headers=request.headers, secret=WEBHOOK_SECRET, tolerance_s=300)
        # TODO: dispatch ev.type to handlers, update DB, etc.
        return Response({"ok": True, "type": ev.type})
    except WebhookVerificationError as e:
        return Response({"ok": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

## URLs

```python
# app/urls.py
from django.urls import path
from . import views, webhooks

urlpatterns = [
    path("api/charges", views.create_charge),
    path("api/subscriptions", views.create_subscription),
    path("webhook/univapay", webhooks.univapay_webhook),
]
```

With this setup, your DRF API can accept tokens from the Univapay widget and create charges/subscriptions server-side, and receive webhook notifications.

