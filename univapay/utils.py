from __future__ import annotations
import uuid
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, localcontext
from typing import Any, Dict, Mapping, Optional

from .debug import dprint, djson

# ==============================================================================
# Currency helpers
# ==============================================================================

# Common ISO currency minor unit exponents.
# (Not exhaustive—defaults to 2 if not listed.)
_CURRENCY_EXPONENTS: Dict[str, int] = {
    # Zero-decimal
    "jpy": 0, "krw": 0, "vnd": 0, "clp": 0, "isk": 0,
    # Two-decimal
    "usd": 2, "eur": 2, "gbp": 2, "cad": 2, "aud": 2, "nzd": 2, "sgd": 2, "hkd": 2,
    "inr": 2, "brl": 2, "mxn": 2, "zar": 2, "sek": 2, "nok": 2, "dkk": 2, "chf": 2,
    "cny": 2, "twd": 2, "thb": 2, "php": 2, "idr": 2, "myr": 2,
    # Three-decimal
    "kwd": 3, "bhd": 3, "jod": 3, "tnd": 3,
}


def normalize_currency(code: str) -> str:
    """
    Normalize an ISO currency code to lowercase.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError("currency code must be a non-empty string")
    c = code.strip().lower()
    dprint("utils.normalize_currency()", {"input": code, "normalized": c})
    return c


def currency_exponent(code: str) -> int:
    """
    Return the minor-unit exponent for a currency (default 2).
    """
    c = normalize_currency(code)
    exp = _CURRENCY_EXPONENTS.get(c, 2)
    dprint("utils.currency_exponent()", {"currency": c, "exponent": exp})
    return exp


def is_zero_decimal_currency(code: str) -> bool:
    """
    True if currency has 0 minor-unit exponent (e.g., JPY).
    """
    return currency_exponent(code) == 0


# ==============================================================================
# Amount conversions (major <-> minor)
# ==============================================================================

def _to_decimal(amount: Decimal | str | int | float) -> Decimal:
    """
    Safely coerce to Decimal. Floats go through str() to avoid binary artifacts.
    """
    if isinstance(amount, Decimal):
        return amount
    if isinstance(amount, int):
        return Decimal(amount)
    if isinstance(amount, float):
        return Decimal(str(amount))
    if isinstance(amount, str):
        try:
            return Decimal(amount.strip())
        except InvalidOperation as e:
            raise ValueError(f"Invalid amount string: {amount!r}") from e
    raise TypeError("amount must be Decimal, str, int, or float")


def quantize_major(amount: Decimal | str | int | float, currency: str) -> Decimal:
    """
    Round a major-unit amount to the correct number of decimal places for `currency`
    using bankers-safe ROUND_HALF_UP (credit-card style).
    """
    exp = currency_exponent(currency)
    dec = _to_decimal(amount)
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        if exp == 0:
            return dec.to_integral_value(rounding=ROUND_HALF_UP)
        # quantize to N decimal places (e.g., 2 -> '0.01', 3 -> '0.001')
        q = Decimal(1).scaleb(-exp)     # == Decimal('1e-<exp>')
        return dec.quantize(q, rounding=ROUND_HALF_UP)


def to_minor_units(amount: Decimal | str | int | float, currency: str) -> int:
    """
    Convert major units to minor (e.g., 12.34 USD -> 1234).
    Accepts Decimal/str/int/float (float is discouraged but supported).

    NOTE: This assumes the input represents MAJOR units.
    """
    exp = currency_exponent(currency)
    dprint("utils.to_minor_units()", {"amount_in": str(amount), "currency": currency, "exp": exp})

    dec = quantize_major(amount, currency)  # ensure correct scale before multiplying
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        scaled = dec * (Decimal(10) ** exp)
        try:
            minor = int(scaled.to_integral_value(rounding=ROUND_HALF_UP))
        except Exception as e:
            raise ValueError(f"Cannot convert amount {amount!r} to minor units") from e

    dprint("utils.to_minor_units() ->", {"minor_out": minor})
    return minor


def from_minor_units(minor: int, currency: str) -> Decimal:
    """
    Convert minor units to major (e.g., 1234 USD -> 12.34).
    """
    if not isinstance(minor, int):
        raise TypeError("minor must be an int")
    exp = currency_exponent(currency)
    dprint("utils.from_minor_units()", {"minor_in": minor, "currency": currency, "exp": exp})
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_UP
        if exp == 0:
            major = Decimal(minor)
        else:
            major = (Decimal(minor) / (Decimal(10) ** exp)).quantize(Decimal(1).scaleb(-exp), rounding=ROUND_HALF_UP)
    dprint("utils.from_minor_units() ->", {"major_out": str(major)})
    return major


def format_major(amount: Decimal | str | int | float, currency: str, *, fixed: bool = True) -> str:
    """
    Format a major-unit amount for display using the currency exponent.

    fixed=True  -> always show the exact number of decimals for the currency.
    fixed=False -> trim trailing zeros (keeps at least one digit after decimal if needed).
    """
    exp = currency_exponent(currency)
    dec = quantize_major(amount, currency)

    if exp == 0:
        return f"{dec:.0f}"

    if fixed:
        fmt = f"{{0:.{exp}f}}"
        return fmt.format(dec)

    # Non-fixed: trim trailing zeros (but keep decimal point if needed)
    s = f"{dec:.{exp}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


# ==============================================================================
# Idempotency keys / UUIDs / time helpers
# ==============================================================================

def make_idempotency_key(prefix: Optional[str] = "unipysdk") -> str:
    """
    Generate a safe Idempotency-Key string. Length kept < 64 chars.
    """
    base = (prefix or "unipysdk").strip() or "unipysdk"
    key = f"{base}_{uuid.uuid4().hex}"
    # Cap length conservatively
    if len(key) > 64:
        key = key[:64]
    dprint("utils.make_idempotency_key()", {"key": key})
    return key


def ensure_idempotency_key(existing: Optional[str], prefix: Optional[str] = "unipysdk") -> str:
    """
    Return existing if provided, otherwise generate a new one.
    """
    if isinstance(existing, str) and existing.strip():
        k = existing.strip()
        dprint("utils.ensure_idempotency_key()", {"existing": k})
        return k
    return make_idempotency_key(prefix=prefix)


def uuid_str() -> str:
    u = uuid.uuid4().hex
    dprint("utils.uuid_str()", {"uuid": u})
    return u


def utcnow_iso() -> str:
    """
    ISO8601 UTC timestamp (seconds precision), e.g. '2025-09-13T12:34:56Z'.
    """
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    dprint("utils.utcnow_iso()", {"ts": ts})
    return ts


# ==============================================================================
# Metadata sanitization
# ==============================================================================

_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, _JSON_PRIMITIVES):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    # Fallback to string
    return str(value)


def safe_metadata(md: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """
    Produce a JSON-serializable metadata dict (keys coerced to str, values converted).
    Useful before sending metadata in API bodies.
    """
    md = md or {}
    if not isinstance(md, Mapping):
        raise TypeError("metadata must be a mapping")
    out = {str(k): _to_json_safe(v) for k, v in md.items()}
    djson("utils.safe_metadata()", out)
    return out


__all__ = [
    # currency helpers
    "normalize_currency",
    "currency_exponent",
    "is_zero_decimal_currency",
    # amount helpers
    "quantize_major",
    "to_minor_units",
    "from_minor_units",
    "format_major",
    # idempotency & time
    "make_idempotency_key",
    "ensure_idempotency_key",
    "uuid_str",
    "utcnow_iso",
    # metadata
    "safe_metadata",
]
