from __future__ import annotations
from typing import Any, Optional, Dict

from .debug import dprint, djson


class UnivapaySDKError(Exception):
    """Base exception for all Univapay SDK errors."""
    pass


class UnivapayConfigError(UnivapaySDKError):
    """Raised when configuration/credentials are invalid or missing."""
    pass


class UnivapayWebhookError(UnivapaySDKError):
    """Raised for webhook signature/format errors."""
    pass


class UnivapayHTTPError(UnivapaySDKError):
    """
    Unified HTTP error for API requests.

    Attributes
    ----------
    status : int
        HTTP status code (or -1 for network errors).
    payload : Any
        Parsed JSON or fallback body describing the error (kept verbatim).
    request_id : Optional[str]
        Server-provided request correlation id, if available.
    method : Optional[str]
        Best-effort HTTP method that triggered the error (if provided).
    url : Optional[str]
        Best-effort URL that triggered the error (if provided).

    Convenience
    -----------
    .code            -> extracted error code (if present in payload)
    .message_text    -> human-friendly error message
    .retryable       -> bool, True if typical transient status (429, 500-504)
    .to_dict()       -> sanitized summary dict for logging
    """

    def __init__(
        self,
        status: int,
        payload: Any,
        request_id: Optional[str] = None,
        *,
        method: Optional[str] = None,
        url: Optional[str] = None,
    ):
        self.status = int(status)
        self.payload = payload
        self.request_id = request_id
        self.method = method
        self.url = url

        # Debug output (payload is printed via djson; avoid leaking secrets)
        dprint("UnivapayHTTPError", {
            "status": self.status,
            "request_id": self.request_id,
            "method": self.method,
            "url": self.url,
        })
        djson("UnivapayHTTPError payload", self.payload)

        super().__init__(self._message())

    # ---------------- convenience properties ----------------

    @property
    def retryable(self) -> bool:
        """Return True for common transient HTTP statuses."""
        return self.status in (429, 500, 502, 503, 504)

    @property
    def code(self) -> Optional[str]:
        """Try to extract a structured error code from the payload if present."""
        p = self.payload
        try:
            if isinstance(p, dict):
                # common shapes: {"code": "..."} or {"error": {"code": "..."}} or {"error_code": "..."}
                if isinstance(p.get("error"), dict) and "code" in p["error"]:
                    return str(p["error"]["code"])
                if "code" in p:
                    return str(p["code"])
                if "error_code" in p:
                    return str(p["error_code"])
            return None
        except Exception:
            return None

    @property
    def message_text(self) -> str:
        """
        Human-friendly message guessed from payload.
        Keeps it short and safe for logs.
        """
        p = self.payload
        # strings straight through
        if isinstance(p, str):
            return p.strip() or "error"
        # dict heuristics
        if isinstance(p, dict):
            for key in ("message", "error", "detail", "description"):
                val = p.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                # nested {"error": {"message": "..."}}
                if isinstance(val, dict):
                    nested = val.get("message") or val.get("detail") or val.get("description")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
            # fallback: very short JSON preview
            try:
                import json
                s = json.dumps(p, ensure_ascii=False)
                return s if len(s) <= 240 else s[:237] + "..."
            except Exception:
                return "error"
        # other types
        try:
            return str(p)
        except Exception:
            return "error"

    # ---------------- rendering & serialization ----------------

    def _message(self) -> str:
        rid = f" req_id={self.request_id}" if self.request_id else ""
        meth = f" {self.method}" if self.method else ""
        url = f" {self.url}" if self.url else ""
        code = f" code={self.code}" if self.code else ""
        msg = self.message_text
        # Keep single-line & compact; payload already printed by djson()
        return f"HTTP {self.status}{meth}{url}{rid}{code}: {msg}"

    def __str__(self) -> str:
        return self._message()

    def __repr__(self) -> str:
        return f"UnivapayHTTPError(status={self.status}, request_id={self.request_id!r}, code={self.code!r})"

    def to_dict(self) -> Dict[str, Any]:
        """Sanitized summary for logs/telemetry; includes only non-sensitive fields."""
        return {
            "status": self.status,
            "request_id": self.request_id,
            "method": self.method,
            "url": self.url,
            "code": self.code,
            "message": self.message_text,
            "retryable": self.retryable,
        }


__all__ = [
    "UnivapaySDKError",
    "UnivapayConfigError",
    "UnivapayHTTPError",
    "UnivapayWebhookError",
]
