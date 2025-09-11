"""
Univapay SDK Client
~~~~~~~~~~~~~~~~~~~

Core API client for interacting with Univapay API.
"""

import json
import logging
from typing import Optional, Dict, Any, List, Union
from decimal import Decimal
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .auth import JWTAuth
from .models import (
    Charge,
    TransactionToken,
    Subscription,
    Customer,
    CreateChargeRequest,
    CreateTokenRequest,
    CreateSubscriptionRequest,
    RefundRequest,
)
from .exceptions import (
    UnivapayError,
    AuthenticationError,
    APIError,
    ValidationError,
    NetworkError,
    RateLimitError,
)


logger = logging.getLogger(__name__)


class UnivapayClient:
    """Main client for interacting with Univapay API."""
    
    DEFAULT_ENDPOINT = "https://api.univapay.com"
    TEST_ENDPOINT = "https://api-test.univapay.com"
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 3
    
    def __init__(
        self,
        app_token: str,
        app_secret: str,
        endpoint: Optional[str] = None,
        test_mode: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        """
        Initialize Univapay client.
        
        Args:
            app_token: Univapay application token
            app_secret: Univapay application secret
            endpoint: API endpoint URL (optional)
            test_mode: Use test endpoint if True
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.auth = JWTAuth(app_token, app_secret)
        
        if endpoint:
            self.base_url = endpoint.rstrip("/")
        elif test_mode or self.auth.is_test_mode():
            self.base_url = self.TEST_ENDPOINT
        else:
            self.base_url = self.DEFAULT_ENDPOINT
        
        self.timeout = timeout
        self.session = self._create_session(max_retries)
        
        logger.info(f"Univapay client initialized with endpoint: {self.base_url}")
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """
        Create a requests session with retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts
        
        Returns:
            Configured requests session
        """
        session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
        
        Returns:
            API response data
        
        Raises:
            Various UnivapayError subclasses based on error type
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self.auth.get_headers()
        
        # Convert Decimal to string for JSON serialization
        if data:
            data = self._serialize_data(data)
        
        logger.debug(f"Making {method} request to {url}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=self.timeout,
            )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", 60)
                raise RateLimitError(
                    message="Rate limit exceeded",
                    retry_after=int(retry_after),
                    http_status=429,
                )
            
            # Check for authentication errors
            if response.status_code == 401:
                raise AuthenticationError(
                    message="Authentication failed",
                    http_status=401,
                    response_data=self._safe_json_parse(response),
                )
            
            # Check for other errors
            if response.status_code >= 400:
                error_data = self._safe_json_parse(response)
                error_message = error_data.get("message", f"API error: {response.status_code}")
                
                raise APIError(
                    message=error_message,
                    http_status=response.status_code,
                    response_data=error_data,
                )
            
            # Parse successful response
            return response.json()
            
        except requests.exceptions.Timeout:
            raise NetworkError(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise NetworkError(f"Request failed: {str(e)}")
    
    def _serialize_data(self, data: Any) -> Any:
        """
        Serialize data for JSON, converting Decimal to string.
        
        Args:
            data: Data to serialize
        
        Returns:
            Serialized data
        """
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, Decimal):
            return str(data)
        elif hasattr(data, "model_dump"):  # Pydantic model
            return self._serialize_data(data.model_dump(by_alias=True, exclude_none=True))
        else:
            return data
    
    def _safe_json_parse(self, response: requests.Response) -> Dict[str, Any]:
        """
        Safely parse JSON response.
        
        Args:
            response: Response object
        
        Returns:
            Parsed JSON or empty dict
        """
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            return {"raw_response": response.text}
    
    # Charge/Payment Methods
    
    def create_charge(
        self,
        transaction_token_id: str,
        amount: Union[int, Decimal],
        currency: str,
        capture: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Charge:
        """
        Create a charge.
        
        Args:
            transaction_token_id: Transaction token ID
            amount: Charge amount
            currency: Currency code (e.g., "JPY")
            capture: Auto-capture the charge (default: True)
            metadata: Additional metadata
        
        Returns:
            Created charge object
        """
        request = CreateChargeRequest(
            transaction_token_id=transaction_token_id,
            amount=Decimal(str(amount)),
            currency=currency,
            capture=capture,
            metadata=metadata,
        )
        
        response = self._make_request("POST", "/charges", data=request)
        return Charge(**response)
    
    def get_charge(self, charge_id: str) -> Charge:
        """
        Get charge details.
        
        Args:
            charge_id: Charge ID
        
        Returns:
            Charge object
        """
        response = self._make_request("GET", f"/charges/{charge_id}")
        return Charge(**response)
    
    def capture_charge(
        self,
        charge_id: str,
        amount: Optional[Union[int, Decimal]] = None,
    ) -> Charge:
        """
        Capture an authorized charge.
        
        Args:
            charge_id: Charge ID
            amount: Amount to capture (None for full amount)
        
        Returns:
            Updated charge object
        """
        data = {}
        if amount is not None:
            data["amount"] = str(amount)
        
        response = self._make_request("POST", f"/charges/{charge_id}/capture", data=data)
        return Charge(**response)
    
    def refund_charge(
        self,
        charge_id: str,
        amount: Optional[Union[int, Decimal]] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Refund a charge.
        
        Args:
            charge_id: Charge ID
            amount: Refund amount (None for full refund)
            reason: Refund reason
            metadata: Additional metadata
        
        Returns:
            Refund response
        """
        request = RefundRequest(
            charge_id=charge_id,
            amount=Decimal(str(amount)) if amount else None,
            reason=reason,
            metadata=metadata,
        )
        
        return self._make_request("POST", f"/charges/{charge_id}/refund", data=request)
    
    # Transaction Token Methods
    
    def create_token(
        self,
        type: str,
        amount: Optional[Union[int, Decimal]] = None,
        currency: Optional[str] = None,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TransactionToken:
        """
        Create a transaction token.
        
        Args:
            type: Token type (one_time, recurring, subscription)
            amount: Token amount
            currency: Currency code
            customer_id: Customer ID
            metadata: Additional metadata
        
        Returns:
            Created transaction token
        """
        request = CreateTokenRequest(
            type=type,
            amount=Decimal(str(amount)) if amount else None,
            currency=currency,
            customer_id=customer_id,
            metadata=metadata,
        )
        
        response = self._make_request("POST", "/tokens", data=request)
        return TransactionToken(**response)
    
    def get_token(self, token_id: str) -> TransactionToken:
        """
        Get transaction token details.
        
        Args:
            token_id: Token ID
        
        Returns:
            Transaction token object
        """
        response = self._make_request("GET", f"/tokens/{token_id}")
        return TransactionToken(**response)
    
    # Subscription Methods
    
    def create_subscription(
        self,
        transaction_token_id: str,
        amount: Union[int, Decimal],
        currency: str,
        billing_cycle: str = "monthly",
        initial_amount: Optional[Union[int, Decimal]] = None,
        customer_id: Optional[str] = None,
        trial_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Subscription:
        """
        Create a subscription.
        
        Args:
            transaction_token_id: Transaction token ID
            amount: Recurring amount
            currency: Currency code
            billing_cycle: Billing cycle (monthly, quarterly, annually)
            initial_amount: Initial payment amount
            customer_id: Customer ID
            trial_days: Trial period in days
            metadata: Additional metadata
        
        Returns:
            Created subscription
        """
        request = CreateSubscriptionRequest(
            transaction_token_id=transaction_token_id,
            amount=Decimal(str(amount)),
            currency=currency,
            billing_cycle=billing_cycle,
            initial_amount=Decimal(str(initial_amount)) if initial_amount else None,
            customer_id=customer_id,
            trial_days=trial_days,
            metadata=metadata,
        )
        
        response = self._make_request("POST", "/subscriptions", data=request)
        return Subscription(**response)
    
    def get_subscription(self, subscription_id: str) -> Subscription:
        """
        Get subscription details.
        
        Args:
            subscription_id: Subscription ID
        
        Returns:
            Subscription object
        """
        response = self._make_request("GET", f"/subscriptions/{subscription_id}")
        return Subscription(**response)
    
    def cancel_subscription(
        self,
        subscription_id: str,
        immediate: bool = False,
    ) -> Subscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription ID
            immediate: Cancel immediately (True) or at end of period (False)
        
        Returns:
            Updated subscription
        """
        data = {"immediate": immediate}
        response = self._make_request("POST", f"/subscriptions/{subscription_id}/cancel", data=data)
        return Subscription(**response)
    
    # Customer Methods
    
    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        """
        Create a customer.
        
        Args:
            email: Customer email
            name: Customer name
            phone: Customer phone
            reference_id: External reference ID
            metadata: Additional metadata
        
        Returns:
            Created customer
        """
        data = {
            "email": email,
            "name": name,
            "phone": phone,
            "referenceId": reference_id,
            "metadata": metadata,
        }
        
        response = self._make_request("POST", "/customers", data=data)
        return Customer(**response)
    
    def get_customer(self, customer_id: str) -> Customer:
        """
        Get customer details.
        
        Args:
            customer_id: Customer ID
        
        Returns:
            Customer object
        """
        response = self._make_request("GET", f"/customers/{customer_id}")
        return Customer(**response)