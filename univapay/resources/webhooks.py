# univapay/resources/webhooks.py
from __future__ import annotations

import hmac
import hashlib
import json
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from pydantic import BaseModel, Field, ConfigDict

from ..debug import dprint, djson


# ------------------------
# Models
# ------------------------

class WebhookEvent(BaseModel):
    """
    Generic Univapay webhook envelope (best-effort typed).
    We keep it permissive so unknown fields won't break you.
    """
    id: Optional[str] = None
    type: Optional[str] = None
    resource_type: Optional[str] = Field(None, alias="resourceType")
    created_on: Optional[str] = Field(None, alias="createdOn")
    created: Optional[str] = None  # some payloads use `created`
    mode: Optional[str] = None     # "test" / "live", etc.

    # Full raw payload for convenience
    data: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class WebhookVerificationError(Exception):
    pass


# ------------------------
# Signature verification
# ------------------------

# Try these header names (case-insensitive). You can override with header_name=...
_SIGNATURE_HEADER_CANDIDATES: Tuple[str, ...] = (
    "X-Univapay-Signature",
    "X-Univapay-Webhook-Signature",
    "X-Signature",
    "X-Hub-Signature-256",   # common pattern elsewhere; included for flexibility
    "X-Hub-Signature",
)

def _get_header(headers: Mapping[str, str], name: str) -> Optional[str]:
    for k, v in headers.items():
        if k.lower() == name.lower():
            return v
    return None

def _find_sig_header(headers: Mapping[str, str], header_name: Optional[str]) -> Tuple[str, str]:
    """
    Return (value, name_found). Raise if not present.
    """
    if header_name:
        val = _get_header(headers, header_name)
        if not val:
            raise WebhookVerificationError(f"signature header '{header_name}' not found")
        return val, header_name

    for candidate in _SIGNATURE_HEADER_CANDIDATES:
        val = _get_header(headers, candidate)
        if val:
            return val, candidate
    raise WebhookVerificationError("no known signature header found")

def _cmp(a: str, b: str) -> bool:
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        return False

def _hmac_hex(secret: Union[str, bytes], payload: Union[str, bytes], algo: str = "sha256") -> str:
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    algo = algo.lower().strip()
    if algo == "sha256":
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()
    if algo == "sha1":
        return hmac.new(secret, payload, hashlib.sha1).hexdigest()
    raise ValueError(f"unsupported hmac algorithm: {algo}")

def _parse_sig_header(sig_value: str) -> Dict[str, str]:
    """
    Parse common formats:
      - "t=TIMESTAMP,v1=HEX"                     (Stripe-like)
      - "sha256=HEX" or "sha1=HEX"               (GitHub-like)
      - "HEX"                                    (raw hex)
    Returns a dict, e.g. {"t": "...", "v1": "..."} or {"sha256": "..."} or {"raw": "..."}.
    """
    parts = [p.strip() for p in sig_value.split(",") if p.strip()]
    kv = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip().lower()] = v.strip()
    if not kv:
        kv["raw"] = sig_value.strip()
    return kv

def verify_signature(
    *,
    payload: Union[str, bytes, bytearray],
    headers: Mapping[str, str],
    secret: Optional[Union[str, bytes]],
    header_name: Optional[str] = None,
    tolerance_s: int = 5 * 60,   # used when header has a timestamp like t=...
    skip_verification: bool = False,
) -> Dict[str, Any]:
    """
    Verify HMAC signatures using common header conventions.
    Returns details dict (including which header matched).
    Raises WebhookVerificationError on failure (unless skip_verification=True).

    DEV NOTE:
      - If `secret` is None/empty and skip_verification=False -> raise.
      - If `skip_verification=True`, we log and return without checking.
    """
    dprint("webhooks.verify_signature() start", {
        "skip_verification": skip_verification,
        "header_name_override": bool(header_name),
        "tolerance_s": tolerance_s,
    })

    if skip_verification:
        dprint("webhooks.verify_signature() skipped (dev mode)")
        return {"skipped": True}

    if not secret:
        raise WebhookVerificationError("webhook secret missing")

    # Find signature header
    sig_value, found_name = _find_sig_header(headers, header_name)
    dprint("webhooks.verify_signature() header found", {"header": found_name, "value_len": len(sig_value)})

    # Normalize payload for hashing
    if isinstance(payload, (bytes, bytearray)):
        body_bytes = bytes(payload)
    else:
        body_bytes = payload.encode("utf-8")

    # Parse header
    parsed = _parse_sig_header(sig_value)
    djson("webhooks.verify_signature() parsed header", parsed)

    ok = False
    reason = "no_match"

    # Case 1: timestamped (t=..., v1=...) - assume v1 is SHA-256 HMAC of "t.<body>"
    if "t" in parsed and "v1" in parsed:
        t_val = parsed["t"]
        sig_hex = parsed["v1"]
        try:
            ts = int(t_val)
            now = int(time.time())
        except Exception as e:
            raise WebhookVerificationError(f"signature verification failed: bad_timestamp:{e}")

        # Enforce tolerance first
        if abs(now - ts) > int(tolerance_s):
            dprint("webhooks.verify_signature() timestamp out of tolerance", {"now": now, "ts": ts})
            raise WebhookVerificationError("signature verification failed: timestamp_out_of_tolerance")

        # canonical message is "<timestamp>.<body>"
        signed_payload = f"{t_val}.".encode("utf-8") + body_bytes
        comp = _hmac_hex(secret, signed_payload, "sha256")
        ok = _cmp(comp, sig_hex)
        if not ok:
            reason = "mismatch"

    # Case 2: sha256=... (GitHub-like)
    elif "sha256" in parsed:
        comp = _hmac_hex(secret, body_bytes, "sha256")
        ok = _cmp(comp, parsed["sha256"])
        if not ok:
            reason = "mismatch"

    # Case 3: sha1=... (rare but supported for flexibility)
    elif "sha1" in parsed:
        comp = _hmac_hex(secret, body_bytes, "sha1")
        ok = _cmp(comp, parsed["sha1"])
        if not ok:
            reason = "mismatch"

    # Case 4: raw hex in header
    elif "raw" in parsed:
        comp = _hmac_hex(secret, body_bytes, "sha256")
        ok = _cmp(comp, parsed["raw"])
        if not ok:
            reason = "mismatch"

    else:
        reason = "unsupported_header_format"

    dprint("webhooks.verify_signature() result", {"ok": ok, "reason": reason, "header": found_name})
    if not ok:
        raise WebhookVerificationError(f"signature verification failed: {reason}")

    return {"ok": True, "header": found_name, "reason": "verified"}


# ------------------------
# Parsing & dispatch
# ------------------------

def parse_event(
    *,
    body: Union[str, bytes, bytearray],
    headers: Mapping[str, str],
    secret: Optional[Union[str, bytes]] = None,
    header_name: Optional[str] = None,
    tolerance_s: int = 5 * 60,
    skip_verification: bool = False,
) -> WebhookEvent:
    """
    Parse and (optionally) verify a Univapay webhook.

    Args:
      body: raw request body (bytes/str).
      headers: incoming HTTP headers (case-insensitive handling).
      secret: your webhook signing secret (None + skip_verification=True for dev).
      header_name: force a specific signature header name (optional).
      tolerance_s: timestamp tolerance when signature contains a timestamp.
      skip_verification: set True for local/dev only.

    Returns:
      WebhookEvent
    """
    dprint("webhooks.parse_event() begin", {
        "skip_verification": skip_verification,
        "header_override": header_name,
    })

    # Verify signature first (unless skipped)
    verify_signature(
        payload=body,
        headers=headers,
        secret=secret,
        header_name=header_name,
        tolerance_s=tolerance_s,
        skip_verification=skip_verification,
    )

    # Decode JSON
    if isinstance(body, (bytes, bytearray)):
        raw_text = body.decode("utf-8", errors="replace")
    else:
        raw_text = body

    try:
        payload = json.loads(raw_text) if raw_text else {}
    except Exception as e:
        raise WebhookVerificationError(f"invalid JSON body: {e}") from e

    djson("webhooks.parse_event() payload", payload)

    # Lift common fields if present
    ev = WebhookEvent(
        id=payload.get("id"),
        type=payload.get("type") or payload.get("event") or payload.get("event_type"),
        resource_type=payload.get("resourceType") or payload.get("resource_type"),
        created_on=payload.get("createdOn") or payload.get("created_on"),
        created=payload.get("created"),
        mode=payload.get("mode"),
        data=payload,
    )
    djson("webhooks.parse_event() event", ev.model_dump(mode="json"))
    return ev


def verify_and_parse(
    *,
    body: Union[str, bytes, bytearray],
    headers: Mapping[str, str],
    secret: Optional[Union[str, bytes]] = None,
    header_name: Optional[str] = None,
    tolerance_s: int = 5 * 60,
    skip_verification: bool = False,
) -> Tuple[Dict[str, Any], WebhookEvent]:
    """
    Convenience: verify_signature(...) + parse_event(...)

    Returns:
      (verify_info_dict, WebhookEvent)
    """
    info = verify_signature(
        payload=body,
        headers=headers,
        secret=secret,
        header_name=header_name,
        tolerance_s=tolerance_s,
        skip_verification=skip_verification,
    )
    event = parse_event(
        body=body,
        headers=headers,
        secret=secret,
        header_name=header_name,
        tolerance_s=tolerance_s,
        skip_verification=True,  # already verified above
    )
    return info, event


# ------------------------
# Tiny event router
# ------------------------

Handler = Callable[[WebhookEvent], Any]

class WebhookRouter:
    """
    Minimal event router:
        router = WebhookRouter()
        @router.on("charge.successful")
        def _h(e): ...
        # wildcard handler:
        @router.on("*")
        def _all(e): ...

        info, event = verify_and_parse(body=..., headers=..., secret=...)
        results = router.dispatch(event)
    """
    def __init__(self) -> None:
        self._map: Dict[str, List[Handler]] = {}

    def on(self, event_type: str) -> Callable[[Handler], Handler]:
        if not event_type or not isinstance(event_type, str):
            raise ValueError("event_type must be a non-empty string (or '*').")

        def _decorator(func: Handler) -> Handler:
            self._map.setdefault(event_type, []).append(func)
            dprint("webhooks.router.on()", {"event_type": event_type, "handler": getattr(func, "__name__", "handler")})
            return func

        return _decorator

    def add(self, event_type: str, func: Handler) -> None:
        self._map.setdefault(event_type, []).append(func)
        dprint("webhooks.router.add()", {"event_type": event_type, "handler": getattr(func, "__name__", "handler")})

    def handlers_for(self, event_type: Optional[str]) -> Iterable[Handler]:
        if not event_type:
            # no type => only wildcard
            return self._map.get("*", [])
        return [*self._map.get(event_type, []), *self._map.get("*", [])]

    def dispatch(self, event: WebhookEvent) -> List[Any]:
        dprint("webhooks.router.dispatch()", {"type": event.type})
        out: List[Any] = []
        for fn in self.handlers_for(event.type):
            try:
                res = fn(event)
                out.append(res)
            except Exception as e:
                dprint("webhooks.router handler error", {"handler": getattr(fn, "__name__", "handler"), "error": repr(e)})
                out.append(e)
        return out


__all__ = [
    "WebhookEvent",
    "WebhookRouter",
    "WebhookVerificationError",
    "parse_event",
    "verify_signature",
    "verify_and_parse",
]
