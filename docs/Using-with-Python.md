# Using with Python

This page covers typical server-side flows using the SDK.

## Setup

```python
from univapay import UnivapayConfig, UnivapayClient

cfg = UnivapayConfig().validate()
client = UnivapayClient(cfg, retries=1, backoff_factor=0.5)
```

## Charges

```python
from univapay.resources import ChargesAPI
from univapay.utils import make_idempotency_key

charges = ChargesAPI(client)

# One-time
ch = charges.create_one_time(
    token_id="token_from_widget",
    amount=12000,
    currency="jpy",
    capture=True,
    idempotency_key=make_idempotency_key("one_time"),
)

# Recurring (token_type=recurring)
ch2 = charges.create_recurring(
    token_id="recurring_token",
    amount=30000,
    currency="jpy",
)

# Read / wait
fetched = charges.get(ch.id)
final = charges.wait_until_terminal(ch.id, server_polling=True)

# Refund
refund = charges.refund(ch.id, amount=6000)
```

## Subscriptions

```python
from univapay.resources import SubscriptionsAPI

subs = SubscriptionsAPI(client)

# Create
s = subs.create(
    token_id="subscription_token",
    amount=59400,
    period="semiannually",
    currency="jpy",
)

# Read / wait
now = subs.get(s.id)
steady = subs.wait_until_terminal(s.id, server_polling=False, timeout_s=120)

# Cancel (with fallback termination_mode if /cancel is not available)
s2 = subs.cancel(s.id, termination_mode="immediate")
```

## Tokens

```python
from univapay.resources import TokensAPI

tokens = TokensAPI(client)
t = tokens.get("transaction_token_id")
print(t.id, t.token_type, t.status)
```

## Webhooks

See [Quickstart](Quickstart.md) for a minimal Flask example. The SDK supports:

- Signature verification (timestamped, sha256, raw hex)
- Permissive event model that keeps unknown fields

## Widgets

```python
from univapay.widgets import (
    build_one_time_widget_config,
    build_subscription_widget_config,
    build_recurring_widget_config,
)

payload = build_subscription_widget_config(
    amount=59400,
    period="semiannually",
    form_id="form-sub",
    button_id="btn-sub",
    description="6 Month Plan",
    payment_methods={"card": True},
)
```

Next steps:

- See [API Reference](API.md) for detailed class/function docs.
- See framework guides: [Django & DRF](Using-with-Django-and-DRF.md), [FastAPI](Using-with-FastAPI.md).

