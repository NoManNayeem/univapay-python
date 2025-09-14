from __future__ import annotations
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Base model: permissive to avoid breaking on API additions
# =============================================================================
class _APIModel(BaseModel):
    """
    Loose model that accepts extra fields so the SDK doesn't break
    when Univapay adds response properties.
    """
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,   # allow using field names when aliases exist
        str_strip_whitespace=True,
    )


# =============================================================================
# Token
# =============================================================================
class TransactionToken(_APIModel):
    """
    Transaction token returned/used by Univapay.
    """
    id: str
    token_type: Optional[str] = Field(None, alias="tokenType")   # "payment" | "recurring" | "subscription"
    status: Optional[str] = None
    # common extras appear in responses but are left permissive via extra="allow"


# =============================================================================
# Charges
# =============================================================================
# Keep as a hint for IDEs; the API uses lower-case values like "successful".
ChargeStatus = Literal["pending", "successful", "failed", "error", "canceled", "authorized", "captured"]

class ChargeCreate(_APIModel):
    """
    Request body for creating a charge.
    """
    transaction_token_id: str = Field(..., description="Transaction token id")
    amount: int
    currency: str = "jpy"
    capture: bool = True

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: int) -> int:
        if not isinstance(v, int) or v <= 0:
            raise ValueError("amount must be a positive integer (minor units).")
        return v

    @field_validator("currency")
    @classmethod
    def _currency_norm(cls, v: str) -> str:
        if not isinstance(v, str) or len(v.strip()) < 3:
            raise ValueError("currency must be an ISO code string, e.g., 'jpy'.")
        return v.strip().lower()


class Charge(_APIModel):
    """
    Charge resource representation.

    The Univapay API often returns `requested_amount/charged_amount` and
    `requested_currency/charged_currency`. Some endpoints may include flat
    `amount/currency`. We accept them all and provide convenience properties.
    """
    id: str

    # Common fields as seen in list/get responses (snake_case from API)
    requested_amount: Optional[int] = Field(None, alias="requested_amount")
    requested_currency: Optional[str] = Field(None, alias="requested_currency")
    charged_amount: Optional[int] = Field(None, alias="charged_amount")
    charged_currency: Optional[str] = Field(None, alias="charged_currency")

    # Fallback flat fields if present on some endpoints
    amount: Optional[int] = None
    currency: Optional[str] = None

    status: Optional[str] = None  # keep permissive; API returns lower-case like "successful"
    transaction_token_id: Optional[str] = Field(None, alias="transaction_token_id")

    @field_validator("currency", "requested_currency", "charged_currency")
    @classmethod
    def _currency_norm(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if isinstance(v, str) else v

    # Convenience accessors for a "best guess" amount/currency
    @property
    def effective_amount(self) -> Optional[int]:
        if self.charged_amount is not None:
            return self.charged_amount
        if self.requested_amount is not None:
            return self.requested_amount
        return self.amount

    @property
    def effective_currency(self) -> Optional[str]:
        if self.charged_currency:
            return self.charged_currency
        if self.requested_currency:
            return self.requested_currency
        return self.currency


# =============================================================================
# Refunds
# =============================================================================
class Refund(_APIModel):
    """
    Refund resource representation.
    """
    id: str
    amount: Optional[int] = None
    status: Optional[str] = None


# =============================================================================
# Subscriptions
# =============================================================================
Period = Literal[
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "bimonthly",
    "quarterly",
    "semiannually",
    "annually",
    "yearly",
]

class SubscriptionCreate(_APIModel):
    """
    Request body for creating a subscription.
    """
    transaction_token_id: str
    amount: int
    currency: str = "jpy"
    period: Period
    start_on: Optional[str] = None  # ISO date

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: int) -> int:
        if not isinstance(v, int) or v <= 0:
            raise ValueError("amount must be a positive integer (minor units).")
        return v

    @field_validator("currency")
    @classmethod
    def _currency_norm(cls, v: str) -> str:
        if not isinstance(v, str) or len(v.strip()) < 3:
            raise ValueError("currency must be an ISO code string, e.g., 'jpy'.")
        return v.strip().lower()


class Subscription(_APIModel):
    """
    Subscription resource representation.

    API responses show e.g.:
      status: "current"
      period: "semiannually"
      currency: "JPY"
    """
    id: str
    amount: int
    currency: str
    period: str
    status: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def _currency_norm(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


# =============================================================================
# Widget envelope (for FE widget config payloads)
# =============================================================================
class WidgetEnvelope(_APIModel):
    """
    The framework-agnostic payload your BE sends to the FE to initialize widgets.
    """
    appId: str
    baseConfig: Dict[str, Any]
    widgets: Dict[str, Dict[str, Any]]
    callbacks: Dict[str, Any]
    api: Dict[str, Any]


__all__ = [
    "TransactionToken",
    "ChargeStatus",
    "ChargeCreate",
    "Charge",
    "Refund",
    "Period",
    "SubscriptionCreate",
    "Subscription",
    "WidgetEnvelope",
]
