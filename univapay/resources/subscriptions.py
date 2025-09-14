from __future__ import annotations
import time
from typing import Any, Dict, Optional

from ..client import UnivapayClient
from ..debug import dprint, djson
from ..models import SubscriptionCreate, Subscription


def _subs_base(client: UnivapayClient) -> str:
    return client._path("subscriptions")


# Terminal-ish statuses (case-insensitive). Includes "current" seen in logs.
_SUB_TERMINAL = {
    s.lower()
    for s in (
        "current",
        "active",
        "canceled",
        "cancelled",
        "failed",
        "error",
        "paused",
        "suspended",
        "inactive",
        "completed",
    )
}


def _is_terminal(status: Optional[str]) -> bool:
    return bool(status and status.strip().lower() in _SUB_TERMINAL)


# ------------------------ validation helpers ------------------------

def _validate_amount(amount: int) -> None:
    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("amount must be a positive integer (minor units).")

def _validate_currency(currency: str) -> str:
    if not isinstance(currency, str) or len(currency.strip()) < 3:
        raise ValueError("currency must be a valid ISO code string, e.g., 'jpy'.")
    return currency.strip().lower()

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
        raise ValueError("period is required (e.g., 'monthly', 'semiannually').")
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

def _validate_token(token_id: str) -> None:
    if not token_id or not isinstance(token_id, str):
        raise ValueError("token_id is required and must be a non-empty string.")

def _validate_id(name: str, value: str) -> None:
    if not value or not isinstance(value, str):
        raise ValueError(f"{name} is required and must be a non-empty string.")


class SubscriptionsAPI:
    """
    Subscriptions API.

    - Create a subscription from a transaction token produced by a **subscription** widget.
    - Use `idempotency_key` on POSTs to avoid dupes on retry.
    - Use `get(..., polling=True)` or `wait_until_terminal(...)` to block until a terminal-ish state.
    - Cancel with `cancel(subscription_id, ...)`.
    """

    def __init__(self, client: UnivapayClient):
        self.client = client
        dprint("subscriptions.__init__()", {"base_path": _subs_base(self.client)})

    # ------------------------ create ------------------------

    def create(
        self,
        *,
        token_id: str,
        amount: int,
        period: str,
        currency: str = "jpy",
        metadata: Optional[Dict[str, Any]] = None,
        start_on: Optional[str] = None,  # ISO date (YYYY-MM-DD)
        idempotency_key: Optional[str] = None,
        **extra: Any,
    ) -> Subscription:
        """Create a subscription using a subscription-capable transaction token."""
        _validate_token(token_id)
        _validate_amount(amount)
        currency = _validate_currency(currency)
        period = _validate_period(period)

        dprint(
            "subscriptions.create()",
            {
                "token_id": token_id,
                "amount": amount,
                "period": period,
                "currency": currency,
                "start_on": start_on,
                "idempotency_key_present": bool(idempotency_key),
            },
        )

        body = SubscriptionCreate(
            transaction_token_id=token_id,
            amount=amount,
            currency=currency,
            period=period,
            start_on=start_on,
        ).model_dump(by_alias=True, exclude_none=True)

        if metadata:
            body["metadata"] = metadata
        body.update(extra or {})

        djson("subscriptions.create body", body)
        resp = self.client.post(_subs_base(self.client), json=body, idempotency_key=idempotency_key)
        return Subscription.model_validate(resp)

    # ------------------------ read ------------------------

    def get(self, subscription_id: str, *, polling: bool = False) -> Subscription:
        """Retrieve a subscription. If polling=True, server may block until steady/terminal state."""
        _validate_id("subscription_id", subscription_id)
        dprint("subscriptions.get()", {"subscription_id": subscription_id, "polling": polling})
        resp = self.client.get(f"{_subs_base(self.client)}/{subscription_id}", polling=polling)
        return Subscription.model_validate(resp)

    # ------------------------ waiter ------------------------

    def wait_until_terminal(
        self,
        subscription_id: str,
        *,
        server_polling: bool = False,  # default False to avoid long blocks by default
        timeout_s: int = 60,
        interval_s: float = 2.0,
    ) -> Subscription:
        """
        Return once the subscription is in a terminal-ish state.

        Flow:
          1) Quick GET without polling; if already terminal-ish (e.g., 'current'), return immediately.
          2) If server_polling=True, do a single GET with polling=true (server may block).
          3) Else, client-side poll until terminal or timeout.
        """
        _validate_id("subscription_id", subscription_id)
        if timeout_s <= 0 or interval_s <= 0:
            raise ValueError("timeout_s and interval_s must be positive.")

        dprint(
            "subscriptions.wait_until_terminal()",
            {
                "subscription_id": subscription_id,
                "server_polling": server_polling,
                "timeout_s": timeout_s,
                "interval_s": interval_s,
            },
        )

        # Step 1: quick check
        sub = self.get(subscription_id, polling=False)
        if _is_terminal(sub.status):
            dprint("subscriptions.wait_until_terminal: already terminal-ish", {"status": sub.status})
            return sub

        # Step 2: server polling if requested
        if server_polling:
            sub_p = self.get(subscription_id, polling=True)
            dprint("subscriptions.wait_until_terminal: server-polling returned", {"status": sub_p.status})
            return sub_p

        # Step 3: client-side loop
        deadline = time.time() + timeout_s
        last = sub
        while time.time() < deadline:
            time.sleep(interval_s)
            last = self.get(subscription_id, polling=False)
            if _is_terminal(last.status):
                dprint("subscriptions.wait_until_terminal: reached terminal-ish", {"status": last.status})
                return last

        dprint(
            "subscriptions.wait_until_terminal timeout",
            {"subscription_id": subscription_id, "last_status": getattr(last, "status", None)},
        )
        return last

    # ------------------------ actions ------------------------

    def cancel(
        self,
        subscription_id: str,
        *,
        idempotency_key: Optional[str] = None,
        termination_mode: Optional[str] = None,
        **extra: Any,
    ) -> Subscription:
        """
        Cancel a subscription and return the updated Subscription resource.

        Primary attempt: POST /subscriptions/{id}/cancel.
        Fallback: PATCH /subscriptions/{id} with {'termination_mode': 'immediate'|'on_next_payment'}
        """
        _validate_id("subscription_id", subscription_id)
        dprint(
            "subscriptions.cancel()",
            {"subscription_id": subscription_id, "idempotency_key_present": bool(idempotency_key)},
        )
        base = _subs_base(self.client)
        path = f"{base}/{subscription_id}/cancel"
        body = {**(extra or {})}
        if termination_mode:
            body.setdefault("termination_mode", termination_mode)
        djson("subscriptions.cancel body", body if body else {})
        try:
            resp = self.client.post(path, json=body, idempotency_key=idempotency_key)
            return Subscription.model_validate(resp)
        except Exception as e:
            # Fallback for accounts without /cancel endpoint
            try:
                from ..errors import UnivapayHTTPError  # local import to avoid cycle
                not_found = isinstance(e, UnivapayHTTPError) and e.status in (404, 405)
            except Exception:
                not_found = False
            if not_found:
                dprint("subscriptions.cancel fallback -> PATCH", {"subscription_id": subscription_id})
                patch_body: Dict[str, Any] = {**(extra or {})}
                patch_body.setdefault("termination_mode", termination_mode or "immediate")
                djson("subscriptions.cancel PATCH body", patch_body)
                resp2 = self.client.patch(f"{base}/{subscription_id}", json=patch_body, idempotency_key=idempotency_key)
                return Subscription.model_validate(resp2)
            raise
