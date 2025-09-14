"""
Univapay-Python SDK

Framework-agnostic helpers for:
- Building FE widget configs (one-time, subscription, recurring)
- One-time / Recurring charges
- Subscriptions (create/get/cancel)
- Refunds & Cancels
- Token reads
- Webhook parsing & signature verification
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Public API re-exports
# ---------------------------------------------------------------------------
from .config import UnivapayConfig
from .client import UnivapayClient
from .errors import (
    UnivapaySDKError,
    UnivapayConfigError,
    UnivapayHTTPError,
    UnivapayWebhookError,
)
from .widgets import (
    build_one_time_widget_config,
    build_subscription_widget_config,
    build_recurring_widget_config,
    widget_loader_src,
    to_json as widget_to_json,
)
from .resources import (
    ChargesAPI,
    SubscriptionsAPI,
    RefundsAPI,
    CancelsAPI,
    TokensAPI,
    # webhook helpers re-exported via resources.__all__
    WebhookEvent,
    WebhookRouter,
    parse_event,
    verify_signature,
    WebhookVerificationError,
)
from .utils import (
    normalize_currency,
    currency_exponent,
    to_minor_units,
    from_minor_units,
    make_idempotency_key,
    ensure_idempotency_key,
    uuid_str,
    utcnow_iso,
    safe_metadata,
)
from .debug import dprint, djson, is_enabled as debug_enabled, set_debug as set_debug_enabled

# ---------------------------------------------------------------------------
# Debug print on import (sanitized; only if UNIVAPAY_DEBUG is truthy)
# ---------------------------------------------------------------------------
dprint("SDK import", {"version": __version__})

__all__ = (
    "__version__",
    # core
    "UnivapayConfig",
    "UnivapayClient",
    # errors
    "UnivapaySDKError",
    "UnivapayConfigError",
    "UnivapayHTTPError",
    "UnivapayWebhookError",
    "WebhookVerificationError",
    # widgets
    "build_one_time_widget_config",
    "build_subscription_widget_config",
    "build_recurring_widget_config",
    "widget_loader_src",
    "widget_to_json",
    # resources
    "ChargesAPI",
    "SubscriptionsAPI",
    "RefundsAPI",
    "CancelsAPI",
    "TokensAPI",
    # webhook helpers
    "WebhookEvent",
    "WebhookRouter",
    "parse_event",
    "verify_signature",
    # utils
    "normalize_currency",
    "currency_exponent",
    "to_minor_units",
    "from_minor_units",
    "make_idempotency_key",
    "ensure_idempotency_key",
    "uuid_str",
    "utcnow_iso",
    "safe_metadata",
    # debug controls
    "dprint",
    "djson",
    "debug_enabled",
    "set_debug_enabled",
)
