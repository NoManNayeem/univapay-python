# Errors and Debugging

## Debug Logging

Set `UNIVAPAY_DEBUG=1` (default during development) to enable SDK debug logs. Logs include sanitized headers and truncated JSON bodies. Set `UNIVAPAY_DEBUG=0` to disable.

Runtime toggles:

```python
from univapay import dprint, djson, set_debug_enabled

set_debug_enabled(True)
```

## Exceptions

- `UnivapaySDKError`: base class for SDK exceptions.
- `UnivapayConfigError`: configuration/credentials issues (e.g., missing `UNIVAPAY_JWT`).
- `UnivapayHTTPError`: unified HTTP error for REST calls.
- `UnivapayWebhookError`: webhook signature/format errors.

### UnivapayHTTPError

Attrs:

- `status`: HTTP status (or `-1` on network errors)
- `payload`: parsed JSON or text fallback
- `request_id`: server-provided request id, if available
- `retryable`: True on 429/500/502/503/504
- `message_text`: a short, user-friendly message derived from payload

```python
from univapay.errors import UnivapayHTTPError

try:
    charge = charges.create_one_time(token_id="...", amount=1000, currency="jpy")
except UnivapayHTTPError as e:
    print(e.status, e.message_text, e.request_id, e.retryable)
    # Optional structured log
    print(e.to_dict())
```

## Rate Limits and Request IDs

Successful responses include a `_meta` field with rate-limit headers (when provided by the API) and the request id. This is helpful for troubleshooting and support.

