# Webhooks

The SDK helps verify signatures, parse events, and dispatch handlers.

## Signature Verification

`verify_signature` accepts common header formats. It tries these header names (case-insensitive) by default:

- `X-Univapay-Signature`
- `X-Univapay-Webhook-Signature`
- `X-Signature`
- `X-Hub-Signature-256`, `X-Hub-Signature`

It supports formats like:

- `t=TIMESTAMP,v1=HEX`
- `sha256=HEX` or `sha1=HEX`
- `HEX` (raw)

Example:

```python
from univapay.resources import verify_signature, WebhookVerificationError

try:
    info = verify_signature(
        payload=raw_body_bytes,
        headers=request_headers,  # mapping of header-name -> value
        secret=WEBHOOK_SECRET,
        tolerance_s=300,
    )
    print(info)  # includes header used, algorithm, computed vs. provided
except WebhookVerificationError as e:
    # return 400
    print("Invalid signature:", str(e))
```

## Parse Event

```python
from univapay.resources import parse_event

ev = parse_event(
    body=raw_body_bytes,
    headers=request_headers,
    secret=WEBHOOK_SECRET,
    tolerance_s=300,
)
print(ev.type, ev.id)
print(ev.data)  # full raw payload
```

## Verify and Parse Together

```python
from univapay.resources import verify_and_parse

info, ev = verify_and_parse(
    body=raw_body_bytes,
    headers=request_headers,
    secret=WEBHOOK_SECRET,
    tolerance_s=300,
)
```

## Tiny Event Router

```python
from univapay.resources import WebhookRouter

router = WebhookRouter()

@router.on("charge.successful")
def on_charge_success(e):
    print("charge successful", e.data.get("id"))

@router.on("*")
def on_any(e):
    print("event:", e.type)

# Later, after verify_and_parse(...)
results = router.dispatch(ev)
```

## Framework Examples

- Flask: see Quickstart and `examples/univapay_flask_demo/`.
- Django/DRF: see Using with Django & DRF.
- FastAPI: see Using with FastAPI.

