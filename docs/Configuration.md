# Configuration

Server-side API calls require both a Univapay App Token (JWT) and a server secret. You can supply them via environment variables or explicitly when constructing `UnivapayConfig`.

## Environment Variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `UNIVAPAY_JWT` | yes | — | FE App Token (JWT). Also used in Authorization with secret. |
| `UNIVAPAY_SECRET` | yes | — | Server secret — keep safe. |
| `UNIVAPAY_STORE_ID` | often | — | Required for most store-scoped calls. |
| `UNIVAPAY_BASE_URL` | no | `https://api.univapay.com` | Set alternative envs. Trailing slash is stripped. |
| `UNIVAPAY_TIMEOUT` | no | `30` | Client timeout (seconds). |
| `UNIVAPAY_DEBUG` | no | `1` | Controls SDK debug logging (1/0). |
| `UNIVAPAY_RETRIES` | no | `0` | Simple retry count for transient errors. |
| `UNIVAPAY_BACKOFF` | no | `0.5` | Exponential backoff factor (seconds). |
| `UNIVAPAY_WIDGET_URL` | no | official | Optional override for widget loader URL. |

Create a `.env` file if you installed with the `dotenv` extra:

```env
UNIVAPAY_JWT=your_app_token_jwt
UNIVAPAY_SECRET=your_server_secret
UNIVAPAY_STORE_ID=your_store_id
UNIVAPAY_BASE_URL=https://api.univapay.com
UNIVAPAY_DEBUG=1
```

## Programmatic Config

```python
from univapay import UnivapayConfig

cfg = UnivapayConfig(
    jwt="...",
    secret="...",
    store_id="...",
    base_url="https://api.univapay.com",
    timeout=30,
    debug=True,
    retries=1,
    backoff_factor=0.5,
).validate()
```

If either `jwt` or `secret` is missing, the SDK raises `UnivapayConfigError`.

## Masked Diagnostics

You can log a safe, masked view of your config for debugging:

```python
print(cfg.masked())
```

The SDK also prints sanitized debug logs when `UNIVAPAY_DEBUG=1`.

