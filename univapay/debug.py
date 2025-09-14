from __future__ import annotations
import os
import json
import datetime
import re
from typing import Any, Dict, Mapping, Optional

# ------------------------------------------------------------------------------
# Debug flag (env overrideable) + runtime toggles
# ------------------------------------------------------------------------------
_DEBUG_ENABLED = os.getenv("UNIVAPAY_DEBUG", "1").lower() not in ("0", "false", "no", "off", "")

def is_enabled() -> bool:
    return _DEBUG_ENABLED

def set_debug(enabled: bool) -> None:
    """Enable/disable debug printing at runtime."""
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = bool(enabled)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
# Case-insensitive "Bearer <token>"
_AUTH_RE = re.compile(r"^bearer\s+(.+)$", re.I)

SENSITIVE_HEADER_KEYS = {"authorization", "x-api-key"}
PARTIAL_MASK_KEYS = {"idempotency-key"}  # not secret, but we still mask most of it

MAX_JSON_CHARS = int(os.getenv("UNIVAPAY_DEBUG_MAX_JSON", "50000"))  # cap printed JSON length

def _ts() -> str:
    # ISO 8601 UTC timestamp, e.g., 2025-09-13T10:20:30Z
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def _mask_value(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}...{val[-2:]}"

def redact_auth(value: Optional[str]) -> Optional[str]:
    """Mask Authorization header while leaving a tiny, non-sensitive hint."""
    if not value:
        return value
    m = _AUTH_RE.match(value.strip())
    if not m:
        return value
    token = m.group(1)
    # If format is "secret.jwt", hide secret and most of the jwt portion
    if "." in token:
        _secret, rest = token.split(".", 1)
        head = rest[:6]
        tail = rest[-4:] if len(rest) > 10 else ""
        return f"Bearer ***.{head}...{tail}"
    # Plain jwt
    head = token[:6]
    tail = token[-4:] if len(token) > 10 else ""
    return f"Bearer ***{head}...{tail}"

def scrub_headers(h: Mapping[str, str]) -> Dict[str, str]:
    """Return a sanitized copy of headers for safe logging."""
    out: Dict[str, str] = {}
    for k, v in (h or {}).items():
        lk = k.lower()
        if lk == "authorization":
            out[k] = redact_auth(v)
        elif lk in SENSITIVE_HEADER_KEYS:
            out[k] = "***"
        elif lk in PARTIAL_MASK_KEYS:
            out[k] = _mask_value(v) or "***"
        else:
            out[k] = v
    return out

# ------------------------------------------------------------------------------
# Printing helpers
# ------------------------------------------------------------------------------
def dprint(*args: Any) -> None:
    if _DEBUG_ENABLED:
        print("[UnivapaySDK]", _ts(), *args, flush=True)

def djson(label: str, data: Any) -> None:
    if _DEBUG_ENABLED:
        try:
            s = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except Exception:
            s = repr(data)
        if len(s) > MAX_JSON_CHARS:
            s = s[:MAX_JSON_CHARS] + "... (truncated)"
        print("[UnivapaySDK]", _ts(), f"{label}:", s, flush=True)
