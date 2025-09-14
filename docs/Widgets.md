# Widgets

The SDK builds FE-safe JSON payloads that your frontend can pass into the official Univapay widget (loader script). These payloads never include secrets and take the App Token (JWT) from env unless you override it explicitly.

See also: `univapay.widgets` in the API reference.

## Loader Script

Default loader URL:

```html
<script src="https://widget.univapay.com/client/checkout.js"></script>
```

Override via env: `UNIVAPAY_WIDGET_URL`.

## One-time Payment

```python
from univapay.widgets import build_one_time_widget_config, to_json

payload = build_one_time_widget_config(
    amount=12000,  # minor units (e.g., JPY)
    form_id="form-one-time",
    button_id="btn-one-time",
    description="Product A - One-time",
    payment_methods={"card": True, "online": {"pay_pay_online": True}},
)
print(to_json(payload, pretty=True))
```

Frontend wiring (vanilla):

```html
<form id="form-one-time" method="POST" action="/charge/one-time">
  <button id="btn-one-time">Pay</button>
\</form>
<script>
  // Render payload from your server (e.g., JSON endpoint).
  // Then initialize the widget with that payload using the official API.
</script>
```

## Subscription

```python
from univapay.widgets import build_subscription_widget_config

payload = build_subscription_widget_config(
    amount=59400,
    period="semiannually",
    form_id="form-sub",
    button_id="btn-sub",
    description="Six-month Plan",
    payment_methods={"card": True},
)
```

## Recurring (Tokenize for Merchant-Initiated Charges)

```python
from univapay.widgets import build_recurring_widget_config

payload = build_recurring_widget_config(
    amount=30000,
    form_id="form-recurring",
    button_id="btn-recurring",
    description="Recurring Billing",
    payment_methods={"card": True},
)
```

## Payment Method Toggles

You can enable/disable categories:

- `card`: `True|False`
- `paidy`: `True|False`
- `konbini`: map of brands (e.g., `{"seven_eleven": True}`)
- `bank_transfer`: map of brands (e.g., `{"japan_post_bank": True}`)
- `online`: map of brands (e.g., `{"pay_pay_online": True, "alipay_online": True}`)

Unknown keys are ignored with a debug note. The frontend is authoritative for filtering.

## Event Hooks (Frontend)

```html
<script>
window.addEventListener("univapay:opened", (e) => console.log("opened", e));
window.addEventListener("univapay:closed", (e) => console.log("closed", e));
window.addEventListener("univapay:success", (e) => {
  console.log("success", e.detail); // tokenId and possibly chargeId/subscriptionId
});
</script>
```

## Bundling Multiple Widgets

```python
from univapay.widgets import (
    build_one_time_widget_config,
    build_subscription_widget_config,
    build_recurring_widget_config,
    build_widget_bundle_envelope,
)

one = build_one_time_widget_config(amount=1000, form_id="f1", button_id="b1", description="A")
sub = build_subscription_widget_config(amount=2000, period="monthly", form_id="f2", button_id="b2", description="B")
rec = build_recurring_widget_config(amount=3000, form_id="f3", button_id="b3", description="C")

bundle = build_widget_bundle_envelope(widgets={
  "oneTimeA": one["widgets"]["oneTime"],
  "subMonthly": sub["widgets"]["subscription"],
  "rec": rec["widgets"]["recurring"],
})
```

