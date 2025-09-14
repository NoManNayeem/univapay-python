# univapay/widgets.py
from __future__ import annotations
import os
import json
from typing import Any, Dict, Mapping, Optional, Tuple, List

# Optional .env loading (safe if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from .debug import dprint, djson  # unified SDK debug printers


# =========================== helpers: env & masking ===========================

def _mask_token(token: Optional[str]) -> str:
    if not token:
        return "(missing)"
    t = token.strip()
    if len(t) <= 10:
        return "***"
    return f"{t[:6]}...{t[-4:]}"


def _require_env_app_id(jwt: Optional[str] = None, env: Mapping[str, str] | None = None) -> str:
    """
    Resolve FE App Token (JWT) for Univapay widget.
    Priority: explicit arg > env['UNIVAPAY_JWT'].
    """
    env = env or os.environ
    val = (jwt or "").strip() or env.get("UNIVAPAY_JWT", "").strip()
    if not val:
        dprint("widgets: no UNIVAPAY_JWT found in args/env")
        raise RuntimeError("UNIVAPAY_JWT not set and no jwt provided.")
    dprint("widgets: appId resolved", {"appId": _mask_token(val)})
    return val


# =========================== helpers: validation ==============================

def _validate_amount(amount: int) -> None:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (minor units, e.g., JPY).")


def _validate_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be a non-empty string.")


_VALID_PERIODS = {
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "bimonthly",
    "quarterly",
    "semiannually",
    "annually",
    "yearly",
}
def _validate_period(period: str) -> str:
    if not isinstance(period, str) or not period.strip():
        raise ValueError("period is required, e.g., 'monthly' or 'semiannually'.")
    raw = period.strip().lower().replace(" ", "")
    alias_map = {
        "year": "annually",
        "yearly": "annually",
        "annual": "annually",
        "annually": "annually",
        "biweekly": "biweekly",
        "bi-weekly": "biweekly",
        "bimonthly": "bimonthly",
        "bi-monthly": "bimonthly",
        "semiannual": "semiannually",
        "semi-annual": "semiannually",
    }
    p = alias_map.get(raw, raw)
    if p not in _VALID_PERIODS:
        raise ValueError(f"period must be one of {sorted(_VALID_PERIODS)}")
    if p == "yearly":
        p = "annually"
    return p


# =========================== helpers: base defaults ===========================

def _normalize_base_config(base_config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    FE-safe defaults; caller can override via base_config.
    """
    merged = {
        "currency": "jpy",
        "locale": "auto",
        "cvvAuthorize": True,   # enables CVV authorize pass-through for recurring cards
    }
    if base_config:
        merged.update(dict(base_config))
    return merged


def _normalize_callbacks(callbacks: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = {
        "enabled": True,
        "logLevel": "info",
    }
    if callbacks:
        merged.update(dict(callbacks))
    return merged


def _normalize_api(api: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    merged = {
        "baseUrl": "/api",
        "endpoints": {"config": "/widget-config", "webhook": "/webhook/univapay"},
    }
    if api:
        merged.update(dict(api))
    return merged


# ====================== helpers: payment method toggles =======================

# Supported categories/brands (SDK-side validation only; FE implements filtering)
_ONLINE_BRANDS = {
    "alipay_online",
    "alipay_plus_online",
    "pay_pay_online",
    "we_chat_online",
    "d_barai_online",
}
_KONBINI_BRANDS = {
    "seven_eleven",
    "family_mart",
    "lawson",
    "mini_stop",
    "seico_mart",
    "pay_easy",  # Pay-easy/ATM/bank kiosk variants
    "daily_yamazaki",
    "yamazaki_daily_store",
}
_BANK_TRANSFER_BRANDS = {"aozora_bank"}  # current documented brand

def _normalize_payment_methods(payment_methods: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Input is a nested dict of booleans like:
      {
        "card": True,
        "paidy": False,
        "online": {"alipay_online": True, "pay_pay_online": False, ...},
        "konbini": {"seven_eleven": True, "lawson": False, ...},
        "bank_transfer": {"aozora_bank": True}
      }

    Output keeps the same shape. Unknown keys are dropped with a debug note.
    """
    if not payment_methods:
        return {}

    out: Dict[str, Any] = {}
    for key, value in payment_methods.items():
        if key == "card":
            out["card"] = bool(value)
        elif key == "paidy":
            out["paidy"] = bool(value)
        elif key == "qr":
            # Allow QR channel toggle passthrough if FE supports it
            out["qr"] = bool(value)
        elif key == "online":
            brands = {}
            if isinstance(value, Mapping):
                for b, on in value.items():
                    if b in _ONLINE_BRANDS:
                        brands[b] = bool(on)
                    else:
                        dprint("widgets: ignoring unknown online brand", {"brand": b})
            out["online"] = brands
        elif key == "konbini":
            brands = {}
            if isinstance(value, Mapping):
                for b, on in value.items():
                    if b in _KONBINI_BRANDS:
                        brands[b] = bool(on)
                    else:
                        dprint("widgets: ignoring unknown konbini brand", {"brand": b})
            out["konbini"] = brands
        elif key == "bank_transfer":
            brands = {}
            if isinstance(value, Mapping):
                for b, on in value.items():
                    if b in _BANK_TRANSFER_BRANDS:
                        brands[b] = bool(on)
                    else:
                        dprint("widgets: ignoring unknown bank brand", {"brand": b})
            out["bank_transfer"] = brands
        else:
            dprint("widgets: ignoring unknown method key", {"key": key})
    return out


def _warn_incompatible(widget_kind: str, methods: Dict[str, Any]) -> None:
    """
    Warn (debug) for obviously incompatible toggles per flow.
    - subscription: primarily card; online/konbini/bank_transfer/paidy typically not used here
    - recurring: card only (tokenize & merchant-initiated charges)
    """
    kind = widget_kind.lower()
    if kind == "subscription":
        for k in ("online", "konbini", "bank_transfer", "paidy"):
            if methods.get(k):
                dprint("widgets: note – non-card method specified for subscription",
                       {"method": k, "advice": "subscription is typically card"})
    if kind == "recurring":
        for k in ("online", "konbini", "bank_transfer", "paidy"):
            if methods.get(k):
                dprint("widgets: note – non-card method specified for recurring",
                       {"method": k, "advice": "recurring is typically card"})


# ============================ envelope (single) ===============================

def _envelope_single(
    *,
    app_id: str,
    widget_key: str,
    widget: Mapping[str, Any],
    base_config: Optional[Mapping[str, Any]] = None,
    callbacks: Optional[Mapping[str, Any]] = None,
    api: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a FE-safe JSON envelope containing a single widget config.
    Do NOT include secrets. Only the FE app token (JWT) is exposed.
    """
    payload = {
        "appId": app_id,
        "baseConfig": _normalize_base_config(base_config),
        "widgets": {widget_key: dict(widget)},
        "callbacks": _normalize_callbacks(callbacks),
        "api": _normalize_api(api),
    }
    dprint("widgets: envelope built", {"widget_key": widget_key})
    djson("widgets.envelope", {**payload, "appId": _mask_token(app_id)})
    return payload


# ============================ envelope (multiple) =============================

def build_widget_bundle_envelope(
    *,
    widgets: Mapping[str, Mapping[str, Any]],
    app_jwt: Optional[str] = None,
    env: Mapping[str, str] | None = None,
    base_config: Optional[Mapping[str, Any]] = None,
    callbacks: Optional[Mapping[str, Any]] = None,
    api: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a single payload with multiple widgets:
      widgets = {
        "oneTimeAlpha": {...},         # result of builders below (already normalized)
        "subscriptionSemiannual": {...},
        "recurringVault": {...}
      }
    """
    app_id = _require_env_app_id(app_jwt, env)
    payload = {
        "appId": app_id,
        "baseConfig": _normalize_base_config(base_config),
        "widgets": {k: dict(v) for k, v in widgets.items()},
        "callbacks": _normalize_callbacks(callbacks),
        "api": _normalize_api(api),
    }
    dprint("widgets: bundle envelope built", {"count": len(widgets)})
    djson("widgets.envelope", {**payload, "appId": _mask_token(app_id)})
    return payload


# ============================ public builders =================================

def build_one_time_widget_config(
    *,
    amount: int,
    form_id: str,
    button_id: str,
    description: str,
    widget_key: str = "oneTime",
    app_jwt: Optional[str] = None,
    env: Mapping[str, str] | None = None,
    base_config: Optional[Mapping[str, Any]] = None,
    callbacks: Optional[Mapping[str, Any]] = None,
    api: Optional[Mapping[str, Any]] = None,
    payment_methods: Optional[Mapping[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build FE config for a ONE-TIME payment widget.
    - Supports enabling/disabling card/paidy/online brands/konbini/bank_transfer via `payment_methods`.
    """
    _validate_amount(amount)
    _validate_id("form_id", form_id)
    _validate_id("button_id", button_id)
    _validate_id("description", description)

    app_id = _require_env_app_id(app_jwt, env)
    methods = _normalize_payment_methods(payment_methods)
    widget = {
        "checkout": "payment",
        "amount": amount,
        "formId": form_id.strip(),
        "buttonId": button_id.strip(),
        "description": description.strip(),
        # New: pass method toggles for FE to filter options
        "paymentMethods": methods,
        **extra,
    }
    dprint("widgets: build_one_time", {"widget_key": widget_key, "amount": amount})
    djson("widgets.one_time.widget", widget)
    return _envelope_single(
        app_id=app_id,
        widget_key=widget_key,
        widget=widget,
        base_config=base_config,
        callbacks=callbacks,
        api=api,
    )


def build_subscription_widget_config(
    *,
    amount: int,
    period: str,                 # e.g., "monthly", "semiannually", "yearly"
    form_id: str,
    button_id: str,
    description: str,
    widget_key: str = "subscription",
    app_jwt: Optional[str] = None,
    env: Mapping[str, str] | None = None,
    base_config: Optional[Mapping[str, Any]] = None,
    callbacks: Optional[Mapping[str, Any]] = None,
    api: Optional[Mapping[str, Any]] = None,
    payment_methods: Optional[Mapping[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build FE config for a SUBSCRIPTION payment widget.
    - Typically card; other methods will be debug-warned if supplied.
    """
    _validate_amount(amount)
    p = _validate_period(period)
    _validate_id("form_id", form_id)
    _validate_id("button_id", button_id)
    _validate_id("description", description)

    app_id = _require_env_app_id(app_jwt, env)
    methods = _normalize_payment_methods(payment_methods)
    _warn_incompatible("subscription", methods)

    widget = {
        "checkout": "payment",
        "tokenType": "subscription",
        "subscriptionPeriod": p,
        "amount": amount,
        "formId": form_id.strip(),
        "buttonId": button_id.strip(),
        "description": description.strip(),
        "paymentMethods": methods,
        **extra,
    }
    dprint("widgets: build_subscription", {"widget_key": widget_key, "amount": amount, "period": p})
    djson("widgets.subscription.widget", widget)
    return _envelope_single(
        app_id=app_id,
        widget_key=widget_key,
        widget=widget,
        base_config=base_config,
        callbacks=callbacks,
        api=api,
    )


def build_recurring_widget_config(
    *,
    amount: int,
    form_id: str,
    button_id: str,
    description: str,
    widget_key: str = "recurring",
    app_jwt: Optional[str] = None,
    env: Mapping[str, str] | None = None,
    base_config: Optional[Mapping[str, Any]] = None,
    callbacks: Optional[Mapping[str, Any]] = None,
    api: Optional[Mapping[str, Any]] = None,
    payment_methods: Optional[Mapping[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build FE config for a RECURRING payment widget (tokenize card for merchant-initiated charges).
    - Recurring is effectively a card-token flow; other methods will be debug-warned if supplied.
    """
    _validate_amount(amount)
    _validate_id("form_id", form_id)
    _validate_id("button_id", button_id)
    _validate_id("description", description)

    app_id = _require_env_app_id(app_jwt, env)
    methods = _normalize_payment_methods(payment_methods)
    _warn_incompatible("recurring", methods)

    widget = {
        "checkout": "payment",
        "tokenType": "recurring",
        "amount": amount,
        "formId": form_id.strip(),
        "buttonId": button_id.strip(),
        "description": description.strip(),
        "paymentMethods": methods,
        **extra,
    }
    dprint("widgets: build_recurring", {"widget_key": widget_key, "amount": amount})
    djson("widgets.recurring.widget", widget)
    return _envelope_single(
        app_id=app_id,
        widget_key=widget_key,
        widget=widget,
        base_config=base_config,
        callbacks=callbacks,
        api=api,
    )


# ============================ loader URL helper ===============================

def widget_loader_src(env: Mapping[str, str] | None = None) -> str:
    """
    Return the official Univapay widget loader URL, optionally overridden by env.

    Env override key: "UNIVAPAY_WIDGET_URL"
    Default: "https://widget.univapay.com/client/checkout.js"
    """
    env = env or os.environ
    return (env.get("UNIVAPAY_WIDGET_URL") or "https://widget.univapay.com/client/checkout.js").strip()


# ============================ JSON convenience ================================

def to_json(payload: Dict[str, Any], *, pretty: bool = False) -> str:
    """
    Serialize any widget envelope to JSON (useful in tests or manual output).
    """
    s = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    dprint("widgets: to_json length", {"chars": len(s)})
    return s


__all__ = [
    "build_one_time_widget_config",
    "build_subscription_widget_config",
    "build_recurring_widget_config",
    "build_widget_bundle_envelope",
    "widget_loader_src",
    "to_json",
]
