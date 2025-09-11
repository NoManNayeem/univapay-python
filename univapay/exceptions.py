"""
Univapay SDK Exceptions
~~~~~~~~~~~~~~~~~~~~~~~

Custom exception classes for the Univapay Python SDK.
"""

from typing import Optional, Dict, Any


class UnivapayError(Exception):
    """Base exception class for all Univapay SDK errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        http_status: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.response_data = response_data or {}

    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class AuthenticationError(UnivapayError):
    """Raised when authentication with Univapay API fails."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, error_code="AUTH_ERROR", **kwargs)


class APIError(UnivapayError):
    """Raised when Univapay API returns an error response."""
    
    def __init__(self, message: str, http_status: int, **kwargs):
        super().__init__(
            message, 
            error_code="API_ERROR", 
            http_status=http_status, 
            **kwargs
        )


class ValidationError(UnivapayError):
    """Raised when request validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        self.field = field
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)


class WebhookVerificationError(UnivapayError):
    """Raised when webhook signature verification fails."""
    
    def __init__(self, message: str = "Webhook signature verification failed", **kwargs):
        super().__init__(message, error_code="WEBHOOK_VERIFICATION_ERROR", **kwargs)


class ConfigurationError(UnivapayError):
    """Raised when SDK configuration is invalid."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)


class TokenExpiredError(UnivapayError):
    """Raised when a transaction token has expired."""
    
    def __init__(self, message: str = "Transaction token has expired", **kwargs):
        super().__init__(message, error_code="TOKEN_EXPIRED", **kwargs)


class PaymentError(UnivapayError):
    """Raised when payment processing fails."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="PAYMENT_ERROR", **kwargs)


class SubscriptionError(UnivapayError):
    """Raised when subscription operation fails."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="SUBSCRIPTION_ERROR", **kwargs)


class RateLimitError(UnivapayError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded", 
        retry_after: Optional[int] = None,
        **kwargs
    ):
        self.retry_after = retry_after
        super().__init__(message, error_code="RATE_LIMIT_ERROR", **kwargs)


class NetworkError(UnivapayError):
    """Raised when network-related errors occur."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="NETWORK_ERROR", **kwargs)