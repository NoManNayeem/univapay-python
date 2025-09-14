# Using with FastAPI

This guide shows how to wire Univapay-Python into a typical FastAPI app.

## Install

```bash
pip install fastapi uvicorn
pip install -e ".[dotenv]"
```

## Settings

Set environment variables (or use a `.env`):

```env
UNIVAPAY_JWT=...
UNIVAPAY_SECRET=...
UNIVAPAY_STORE_ID=...
UNIVAPAY_BASE_URL=https://api.univapay.com
```

## Client dependency

```python
# deps.py
from univapay import UnivapayConfig, UnivapayClient

def get_client() -> UnivapayClient:
    cfg = UnivapayConfig().validate()
    return UnivapayClient(cfg, retries=1, backoff_factor=0.5)
```

## Routes

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from univapay.resources import ChargesAPI, SubscriptionsAPI, parse_event, WebhookVerificationError
from .deps import get_client

app = FastAPI()

@app.post("/api/charges")
async def create_charge(payload: dict, client = Depends(get_client)):
    token_id = payload.get("tokenId")
    amount = int(payload.get("amount", 0))
    currency = payload.get("currency", "jpy")
    if not token_id or amount <= 0:
        raise HTTPException(status_code=400, detail="tokenId and amount required")
    with client as c:
        ch = ChargesAPI(c).create_one_time(token_id=token_id, amount=amount, currency=currency)
        return ch.model_dump()

@app.post("/api/subscriptions")
async def create_subscription(payload: dict, client = Depends(get_client)):
    token_id = payload.get("tokenId")
    amount = int(payload.get("amount", 0))
    currency = payload.get("currency", "jpy")
    period = payload.get("period")
    if not token_id or amount <= 0 or not period:
        raise HTTPException(status_code=400, detail="tokenId, amount, period required")
    with client as c:
        s = SubscriptionsAPI(c).create(token_id=token_id, amount=amount, period=period, currency=currency)
        return s.model_dump()

@app.post("/webhook/univapay")
async def webhook(request: Request):
    body = await request.body()
    try:
        ev = parse_event(body=body, headers=request.headers, secret=None, tolerance_s=300, skip_verification=True)
        # TODO: dispatch `ev.type` to handlers, update DB, etc.
        return {"ok": True, "type": ev.type}
    except WebhookVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

Run the app:

```bash
uvicorn main:app --reload
```

Use the SDK’s widget builders on the server to create FE-safe JSON payloads for your frontend to pass into the official Univapay widget.

