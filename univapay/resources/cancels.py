from __future__ import annotations
from typing import Any, Optional

from ..client import UnivapayClient
from ..debug import dprint, djson
from ..models import Charge


def _validate_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required and must be a non-empty string.")


class CancelsAPI:
    """
    Cancel helpers for charges (authorization/charge cancel).

    Most accounts use:
        POST /charges/{charge_id}/cancel

    Depending on your capture flow, this may be equivalent to voiding an
    authorization. This SDK provides a `void_authorization` alias for clarity.
    """

    def __init__(self, client: UnivapayClient):
        self.client = client

    def cancel_charge(
        self,
        charge_id: str,
        *,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Charge:
        """
        Cancel a charge (or an authorization prior to capture).

        Parameters
        ----------
        charge_id : str
            The charge identifier to cancel.
        idempotency_key : Optional[str]
            Recommended for safe retries.
        **extra :
            Additional fields supported by your Univapay account.

        Returns
        -------
        Charge
            The canceled/voided charge resource (typed).
        """
        _validate_id("charge_id", charge_id)

        path = f"{self.client._path('charges')}/{charge_id}/cancel"
        dprint(
            "cancels.cancel_charge()",
            {"charge_id": charge_id, "idempotency_key_present": bool(idempotency_key)},
        )
        body = {**extra} if extra else {}
        djson("cancels.cancel_charge body", body)

        resp = self.client.post(path, json=body, idempotency_key=idempotency_key)
        return Charge.model_validate(resp)

    # ---------------------------------------------------------------------
    # Alias for accounts that conceptually distinguish "void" vs "cancel".
    # This calls the same endpoint as `cancel_charge` by default.
    # ---------------------------------------------------------------------
    def void_authorization(
        self,
        charge_id: str,
        *,
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Charge:
        """
        Void a previously authorized (not yet captured) charge.

        Notes
        -----
        Many Univapay setups map this to the same route as cancel:
            POST /charges/{charge_id}/cancel

        Returns
        -------
        Charge
        """
        dprint("cancels.void_authorization() -> cancel_charge()", {"charge_id": charge_id})
        return self.cancel_charge(
            charge_id,
            idempotency_key=idempotency_key,
            **extra,
        )


__all__ = ["CancelsAPI"]
