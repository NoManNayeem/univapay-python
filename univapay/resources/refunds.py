from __future__ import annotations
import time
from typing import Any, Dict, Optional

from ..client import UnivapayClient
from ..debug import dprint, djson
from ..models import Refund

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _base(client: UnivapayClient, charge_id: str) -> str:
    return f"{client._path('charges')}/{charge_id}/refunds"

def _validate_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be a non-empty string.")

def _validate_amount(amount: int) -> None:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (minor units).")

# Terminal-ish statuses (case-insensitive; broad to be safe)
_REFUND_TERMINAL = {s.lower() for s in ("successful", "failed", "error", "canceled", "cancelled")}
def _is_terminal(status: Optional[str]) -> bool:
    return bool(status and status.strip().lower() in _REFUND_TERMINAL)

# ------------------------------------------------------------------------------
# API
# ------------------------------------------------------------------------------

class RefundsAPI:
    """
    Refunds API (per-charge).

    Common flows:
      - Create a refund for a given charge (full refund if `amount` omitted and your account allows it).
      - Get a specific refund (optionally with server-side polling).
      - List refunds for a charge (basic pagination passthrough).
      - Wait until a refund reaches a terminal status.
    """

    def __init__(self, client: UnivapayClient):
        self.client = client

    # ---- Create ----
    def create(
        self,
        charge_id: str,
        *,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Refund:
        """
        Create a refund.

        Parameters
        ----------
        charge_id : str
            The charge to refund.
        amount : Optional[int]
            Amount in minor units. If None, a full refund may be performed (API/account dependent).
        reason : Optional[str]
            Optional reason string for audit trails.
        idempotency_key : Optional[str]
            Recommended: pass a stable id for safe retries.

        Returns
        -------
        Refund
        """
        _validate_id("charge_id", charge_id)
        if amount is not None:
            _validate_amount(amount)

        payload: Dict[str, Any] = {}
        if amount is not None:
            payload["amount"] = amount
        if reason:
            payload["reason"] = reason
        payload.update(extra)

        dprint(
            "refunds.create()",
            {
                "charge_id": charge_id,
                "amount": amount,
                "reason": reason,
                "idempotency_key_present": bool(idempotency_key),
            },
        )
        djson("refunds.create body", payload)

        resp = self.client.post(_base(self.client, charge_id), json=payload, idempotency_key=idempotency_key)
        return Refund.model_validate(resp)

    def create_full_refund(
        self,
        charge_id: str,
        *,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Refund:
        """
        Convenience: request a full refund (omit `amount`).
        """
        dprint("refunds.create_full_refund()", {"charge_id": charge_id})
        return self.create(
            charge_id,
            amount=None,
            reason=reason,
            idempotency_key=idempotency_key,
            **extra,
        )

    def create_partial_refund(
        self,
        charge_id: str,
        *,
        amount: int,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Refund:
        """
        Convenience: request a partial refund (requires `amount`).
        """
        dprint("refunds.create_partial_refund()", {"charge_id": charge_id, "amount": amount})
        _validate_amount(amount)
        return self.create(
            charge_id,
            amount=amount,
            reason=reason,
            idempotency_key=idempotency_key,
            **extra,
        )

    # ---- Read ----
    def get(self, charge_id: str, refund_id: str, *, polling: bool = False) -> Refund:
        """
        Fetch a specific refund. If `polling=True`, server may block until a terminal state (when supported).
        """
        _validate_id("charge_id", charge_id)
        _validate_id("refund_id", refund_id)

        path = f"{_base(self.client, charge_id)}/{refund_id}"
        dprint("refunds.get()", {"charge_id": charge_id, "refund_id": refund_id, "polling": polling})
        resp = self.client.get(path, polling=polling)
        return Refund.model_validate(resp)

    # ---- List ----
    def list(
        self,
        charge_id: str,
        *,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        List refunds for a charge (passthrough dict to preserve API fields/pagination).
        """
        _validate_id("charge_id", charge_id)

        params: Dict[str, Any] = {}
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("limit must be a positive integer.")
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        if extra_params:
            params.update(extra_params)

        dprint("refunds.list()", {"charge_id": charge_id, "params": params})
        resp = self.client.get(_base(self.client, charge_id), params=params)
        djson("refunds.list response", resp)
        return resp

    # ---- Wait until terminal ----
    def wait_until_terminal(
        self,
        charge_id: str,
        refund_id: str,
        *,
        server_polling: bool = True,
        timeout_s: int = 60,
        interval_s: float = 2.0,
    ) -> Refund:
        """
        Block until the refund reaches a terminal-ish status.

        If server_polling=True, perform a single GET with polling=true.
        Otherwise, poll client-side every `interval_s` until `timeout_s` is reached.
        """
        _validate_id("charge_id", charge_id)
        _validate_id("refund_id", refund_id)
        if timeout_s <= 0 or interval_s <= 0:
            raise ValueError("timeout_s and interval_s must be positive.")

        dprint(
            "refunds.wait_until_terminal()",
            {
                "charge_id": charge_id,
                "refund_id": refund_id,
                "server_polling": server_polling,
                "timeout_s": timeout_s,
                "interval_s": interval_s,
            },
        )

        if server_polling:
            # Single blocking call if the API supports server-side polling
            return self.get(charge_id, refund_id, polling=True)

        # Client-side polling loop
        deadline = time.time() + timeout_s
        last = self.get(charge_id, refund_id, polling=False)
        if _is_terminal(last.status):
            dprint("refunds.wait_until_terminal: already terminal-ish", {"status": last.status})
            return last

        while time.time() < deadline:
            time.sleep(interval_s)
            last = self.get(charge_id, refund_id, polling=False)
            if _is_terminal(last.status):
                dprint("refunds.wait_until_terminal -> terminal-ish", {"status": last.status})
                return last

        dprint("refunds.wait_until_terminal -> timeout", {"last_status": getattr(last, "status", None)})
        return last
