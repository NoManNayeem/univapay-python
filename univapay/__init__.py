"""
Univapay Python SDK
~~~~~~~~~~~~~~~~~~~

A Python SDK for Univapay payment platform supporting Flask, Django, and FastAPI.

Basic usage:
    >>> from univapay import UnivapayClient
    >>> client = UnivapayClient(app_token='your-token', app_secret='your-secret')
    >>> charge = client.create_charge(transaction_token_id='token-id', amount=1000, currency='JPY')

Widget usage:
    >>> from univapay import UnivapayWidget
    >>> widget = UnivapayWidget(app_token='your-token')
    >>> html = widget.render_html(amount=1000, currency='JPY')
"""

__version__ = "0.1.0"
__author__ = "Nayeem Islam"
__email__ = "islam.nayeem@outlook.com"

from .client import UnivapayClient
from .widget import UnivapayWidget
from .exceptions import (
    UnivapayError,
    AuthenticationError,
    APIError,
    ValidationError,
    WebhookVerificationError,
)
from .models import (
    Charge,
    TransactionToken,
    Subscription,
    Customer,
    WebhookEvent,
)
from .webhook import WebhookHandler

__all__ = [
    "UnivapayClient",
    "UnivapayWidget",
    "UnivapayError",
    "AuthenticationError",
    "APIError",
    "ValidationError",
    "WebhookVerificationError",
    "Charge",
    "TransactionToken",
    "Subscription",
    "Customer",
    "WebhookEvent",
    "WebhookHandler",
]

# Set default logging handler to avoid "No handler found" warnings.
import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())