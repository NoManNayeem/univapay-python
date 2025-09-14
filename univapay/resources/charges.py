from __future__ import annotations
import time
from typing import Any, Dict, Optional

from ..client import UnivapayClient
from ..debug import dprint, djson
from ..models import ChargeCreate, Charge, Refund


def _charges_base(client: UnivapayClient) -> str:
    return client._path("charges")


# API tends to return lower-case statuses like "successful".
# We normalize comparisons to lower-case to be safe.
_TERMINAL_STATES = {
    "successful",
    "failed",
    "error",
    "canceled",
    "captured",   # seen on some flows
    # "authorized" is typically NOT terminal; omit unless your flow considers it terminal
}


# ----------------------- validation helpers -----------------------

def _validate_amount(amount: int) -> None:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (minor units, e.g., JPY).")

def _validate_currency(currency: str) -> str:
    if not isinstance(currency, str) or len(currency.strip()) < 3:
        raise ValueError("currency must be a valid ISO code string (e.g., 'jpy').")
    return currency.strip().lower()

def _validate_token(token_id: str) -> None:
    if not token_id or not isinstance(token_id, str):
        raise ValueError("token_id is required and must be a non-empty string.")

def _validate_id(name: str, value: str) -> None:
    if not value or not isinstance(value, str):
        raise ValueError(f"{name} is required and must be a non-empty string.")


class ChargesAPI:
    """
    One-time & recurring charges API.

    Notes:
      - For one-time: pass a transaction token produced by a one-time widget.
      - For recurring: pass a transaction token produced by a 'recurring' widget.
      - Use `idempotency_key` on POSTs to avoid duplicate charges on retries.
      - Use `get(..., polling=True)` or `wait_until_terminal(...)` to block until a terminal status.
    """

    def __init__(self, client: UnivapayClient):
        self.client = client
        dprint("charges.__init__()", {"base_path": _charges_base(self.client)})

    # ----------------------- create: one-time -----------------------

    def create_one_time(
        self,
        *,
        token_id: str,
        amount: int,
        currency: str = "jpy",
        capture: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Charge:
        """
        Create a one-time charge using a one-time transaction token.
        """
        _validate_token(token_id)
        _validate_amount(amount)
        currency = _validate_currency(currency)

        dprint("charges.create_one_time()", {
            "token_id": token_id,
            "amount": amount,
            "currency": currency,
            "capture": capture,
            "idempotency_key_present": bool(idempotency_key),
        })

        body = ChargeCreate(
            transaction_token_id=token_id,
            amount=amount,
            currency=currency,
            capture=capture,
        ).model_dump(by_alias=True)

        if metadata:
            body["metadata"] = metadata
        body.update(extra or {})

        djson("charges.create_one_time body", body)
        resp = self.client.post(_charges_base(self.client), json=body, idempotency_key=idempotency_key)
        return Charge.model_validate(resp)

    # ----------------------- create: recurring -----------------------

    def create_recurring(
        self,
        *,
        token_id: str,
        amount: int,
        currency: str = "jpy",
        capture: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Charge:
        """
        Create a charge using a **recurring** transaction token.
        Endpoint is the same as one-time; the server enforces token type.
        """
        _validate_token(token_id)
        _validate_amount(amount)
        currency = _validate_currency(currency)

        dprint("charges.create_recurring()", {
            "token_id": token_id,
            "amount": amount,
            "currency": currency,
            "capture": capture,
            "idempotency_key_present": bool(idempotency_key),
        })

        # Delegate to the same creation logic to keep behavior identical.
        return self.create_one_time(
            token_id=token_id,
            amount=amount,
            currency=currency,
            capture=capture,
            metadata=metadata,
            idempotency_key=idempotency_key,
            **(extra or {}),
        )

    # ----------------------- read -----------------------

    def get(self, charge_id: str, *, polling: bool = False) -> Charge:
        """
        Retrieve a charge. If polling=True, server blocks until a terminal state when supported.
        """
        _validate_id("charge_id", charge_id)
        dprint("charges.get()", {"charge_id": charge_id, "polling": polling})
        resp = self.client.get(f"{_charges_base(self.client)}/{charge_id}", polling=polling)
        return Charge.model_validate(resp)

    # ----------------------- waiter -----------------------

    def wait_until_terminal(
        self,
        charge_id: str,
        *,
        server_polling: bool = True,
        timeout_s: int = 90,
        interval_s: float = 2.0,
    ) -> Charge:
        """
        Block until the charge reaches a terminal state.

        If server_polling=True, perform a single GET with polling=true.
        Otherwise, poll client-side every interval_s until timeout_s is reached.
        """
        _validate_id("charge_id", charge_id)
        if timeout_s <= 0 or interval_s <= 0:
            raise ValueError("timeout_s and interval_s must be positive.")

        dprint("charges.wait_until_terminal()", {
            "charge_id": charge_id,
            "server_polling": server_polling,
            "timeout_s": timeout_s,
            "interval_s": interval_s,
        })

        if server_polling:
            ch = self.get(charge_id, polling=True)
            dprint("charges.wait_until_terminal: server-polling returned", {"status": ch.status})
            return ch

        deadline = time.time() + timeout_s
        while True:
            ch = self.get(charge_id)
            status_norm = (ch.status or "").lower()
            if status_norm in _TERMINAL_STATES:
                dprint("charges.wait_until_terminal -> terminal", {"status": ch.status})
                return ch
            if time.time() >= deadline:
                dprint("charges.wait_until_terminal -> timeout", {"last_status": ch.status})
                return ch
            time.sleep(interval_s)

    # ----------------------- actions -----------------------

    def refund(
        self,
        charge_id: str,
        *,
        amount: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Refund:
        """
        Create a refund for a charge. If `amount` is None, a full refund may be performed (API-dependent).
        """
        _validate_id("charge_id", charge_id)
        if amount is not None:
            _validate_amount(amount)

        dprint("charges.refund()", {
            "charge_id": charge_id,
            "amount": amount,
            "idempotency_key_present": bool(idempotency_key),
        })

        path = f"{_charges_base(self.client)}/{charge_id}/refunds"
        body: Dict[str, Any] = {"amount": amount} if amount is not None else {}
        djson("charges.refund body", body)
        resp = self.client.post(path, json=body, idempotency_key=idempotency_key)
        return Refund.model_validate(resp)

    def capture(self, charge_id: str, *, idempotency_key: Optional[str] = None, **extra: Any) -> Charge:
        """
        Capture a previously authorized charge (if your account flow supports auth/capture).
        """
        _validate_id("charge_id", charge_id)
        dprint("charges.capture()", {"charge_id": charge_id, "idempotency_key_present": bool(idempotency_key)})
        path = f"{_charges_base(self.client)}/{charge_id}/capture"
        djson("charges.capture body", {**extra} if extra else {})
        resp = self.client.post(path, json={**(extra or {})}, idempotency_key=idempotency_key)
        return Charge.model_validate(resp)

    def cancel(self, charge_id: str, *, idempotency_key: Optional[str] = None, **extra: Any) -> Charge:
        """
        Cancel (void) a charge. Route name may vary by capture flow; adjust if needed.
        """
        _validate_id("charge_id", charge_id)
        dprint("charges.cancel()", {"charge_id": charge_id, "idempotency_key_present": bool(idempotency_key)})
        path = f"{_charges_base(self.client)}/{charge_id}/cancel"
        djson("charges.cancel body", {**extra} if extra else {})
        resp = self.client.post(path, json={**(extra or {})}, idempotency_key=idempotency_key)
        return Charge.model_validate(resp)
