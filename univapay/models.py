"""
Univapay SDK Data Models
~~~~~~~~~~~~~~~~~~~~~~~~

Pydantic models for request/response data structures.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


class Currency(str, Enum):
    """Supported currencies."""
    JPY = "JPY"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AUD = "AUD"
    CAD = "CAD"
    SGD = "SGD"
    HKD = "HKD"
    CNY = "CNY"
    KRW = "KRW"
    THB = "THB"
    MYR = "MYR"
    PHP = "PHP"
    IDR = "IDR"
    VND = "VND"


class PaymentStatus(str, Enum):
    """Payment status values."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TokenType(str, Enum):
    """Token type values."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    SUBSCRIPTION = "subscription"


class CheckoutType(str, Enum):
    """Checkout type values."""
    PAYMENT = "payment"
    TOKEN = "token"
    SUBSCRIPTION = "subscription"


class SubscriptionStatus(str, Enum):
    """Subscription status values."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class BaseResponse(BaseModel):
    """Base response model."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )


class TransactionToken(BaseResponse):
    """Transaction token model."""
    id: str
    type: TokenType
    amount: Optional[Decimal] = None
    currency: Optional[Currency] = None
    created_at: datetime = Field(alias="createdAt")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class Charge(BaseResponse):
    """Charge/Payment model."""
    id: str
    transaction_token_id: str = Field(alias="transactionTokenId")
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    authorized: bool = False
    captured: bool = False
    refunded: bool = False
    refunded_amount: Optional[Decimal] = Field(None, alias="refundedAmount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", "refunded_amount", mode="before")
    @classmethod
    def validate_decimal(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class Customer(BaseResponse):
    """Customer model."""
    id: str
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    reference_id: Optional[str] = Field(None, alias="referenceId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    metadata: Optional[Dict[str, Any]] = None


class Subscription(BaseResponse):
    """Subscription model."""
    id: str
    customer_id: Optional[str] = Field(None, alias="customerId")
    transaction_token_id: str = Field(alias="transactionTokenId")
    status: SubscriptionStatus
    amount: Decimal
    currency: Currency
    initial_amount: Optional[Decimal] = Field(None, alias="initialAmount")
    billing_cycle: str = Field(alias="billingCycle")  # monthly, quarterly, annually
    next_billing_date: Optional[datetime] = Field(None, alias="nextBillingDate")
    trial_end_date: Optional[datetime] = Field(None, alias="trialEndDate")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    cancelled_at: Optional[datetime] = Field(None, alias="cancelledAt")
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", "initial_amount", mode="before")
    @classmethod
    def validate_decimal(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class WebhookEvent(BaseResponse):
    """Webhook event model."""
    id: str
    event: str  # charge.created, charge.captured, subscription.created, etc.
    created_at: datetime = Field(alias="createdAt")
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class CreateChargeRequest(BaseModel):
    """Request model for creating a charge."""
    transaction_token_id: str
    amount: Decimal
    currency: Currency
    capture: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        return Decimal(str(v))


class CreateTokenRequest(BaseModel):
    """Request model for creating a transaction token."""
    type: TokenType
    amount: Optional[Decimal] = None
    currency: Optional[Currency] = None
    customer_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription."""
    transaction_token_id: str
    amount: Decimal
    currency: Currency
    initial_amount: Optional[Decimal] = None
    billing_cycle: str = "monthly"  # monthly, quarterly, annually
    customer_id: Optional[str] = None
    trial_days: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", "initial_amount", mode="before")
    @classmethod
    def validate_decimal(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class RefundRequest(BaseModel):
    """Request model for creating a refund."""
    charge_id: str
    amount: Optional[Decimal] = None  # None for full refund
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v