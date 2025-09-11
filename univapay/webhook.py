"""
Univapay SDK Webhook Handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Webhook signature verification and event handling.
"""

import hashlib
import hmac
import json
import logging
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime

from .models import WebhookEvent
from .exceptions import WebhookVerificationError, ValidationError


logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handler for Univapay webhook events."""
    
    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize webhook handler.
        
        Args:
            webhook_secret: Secret key for webhook signature verification
        """
        self.webhook_secret = webhook_secret
        self.event_handlers: Dict[str, Callable] = {}
        
    def verify_signature(
        self,
        payload: Union[str, bytes, Dict[str, Any]],
        signature: str,
        secret: Optional[str] = None,
    ) -> bool:
        """
        Verify webhook signature using HMAC-SHA256.
        
        Args:
            payload: Webhook payload (raw body string or dict)
            signature: Signature from X-Signature header
            secret: Webhook secret (uses instance secret if not provided)
        
        Returns:
            True if signature is valid
        
        Raises:
            WebhookVerificationError: If signature is invalid
        """
        secret = secret or self.webhook_secret
        
        if not secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True
        
        # Convert payload to bytes if needed
        if isinstance(payload, dict):
            payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        elif isinstance(payload, str):
            payload_bytes = payload.encode("utf-8")
        else:
            payload_bytes = payload
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (constant time comparison)
        is_valid = hmac.compare_digest(expected_signature, signature)
        
        if not is_valid:
            logger.error("Webhook signature verification failed")
            raise WebhookVerificationError(
                f"Invalid signature. Expected: {expected_signature[:8]}..., Got: {signature[:8]}..."
            )
        
        logger.debug("Webhook signature verified successfully")
        return True
    
    def parse_event(self, payload: Union[str, Dict[str, Any]]) -> WebhookEvent:
        """
        Parse webhook event from payload.
        
        Args:
            payload: Webhook payload (JSON string or dict)
        
        Returns:
            Parsed webhook event
        
        Raises:
            ValidationError: If payload is invalid
        """
        try:
            if isinstance(payload, str):
                data = json.loads(payload)
            else:
                data = payload
            
            # Ensure required fields
            if "event" not in data:
                raise ValidationError("Missing 'event' field in webhook payload")
            
            if "id" not in data:
                raise ValidationError("Missing 'id' field in webhook payload")
            
            # Parse the event
            event = WebhookEvent(**data)
            
            logger.info(f"Parsed webhook event: {event.event} (ID: {event.id})")
            return event
            
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in webhook payload: {str(e)}")
        except Exception as e:
            raise ValidationError(f"Failed to parse webhook event: {str(e)}")
    
    def handle_webhook(
        self,
        payload: Union[str, Dict[str, Any]],
        signature: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> WebhookEvent:
        """
        Handle incoming webhook.
        
        Args:
            payload: Webhook payload
            signature: Signature from X-Signature header
            headers: Request headers
        
        Returns:
            Processed webhook event
        
        Raises:
            WebhookVerificationError: If signature verification fails
            ValidationError: If payload is invalid
        """
        # Extract signature from headers if not provided
        if signature is None and headers:
            signature = headers.get("X-Signature") or headers.get("x-signature")
        
        # Verify signature if provided
        if signature and self.webhook_secret:
            self.verify_signature(payload, signature)
        
        # Parse event
        event = self.parse_event(payload)
        
        # Dispatch to registered handlers
        self._dispatch_event(event)
        
        return event
    
    def register_handler(self, event_type: str, handler: Callable[[WebhookEvent], None]):
        """
        Register an event handler.
        
        Args:
            event_type: Event type to handle (e.g., "charge.created")
            handler: Callback function to handle the event
        """
        self.event_handlers[event_type] = handler
        logger.debug(f"Registered handler for event type: {event_type}")
    
    def on(self, event_type: str):
        """
        Decorator for registering event handlers.
        
        Usage:
            @webhook_handler.on("charge.created")
            def handle_charge_created(event):
                print(f"Charge created: {event.id}")
        
        Args:
            event_type: Event type to handle
        
        Returns:
            Decorator function
        """
        def decorator(func: Callable):
            self.register_handler(event_type, func)
            return func
        return decorator
    
    def _dispatch_event(self, event: WebhookEvent):
        """
        Dispatch event to registered handlers.
        
        Args:
            event: Webhook event to dispatch
        """
        # Try specific event handler
        if event.event in self.event_handlers:
            try:
                self.event_handlers[event.event](event)
                logger.debug(f"Dispatched event {event.event} to specific handler")
            except Exception as e:
                logger.error(f"Error in event handler for {event.event}: {str(e)}")
                raise
        
        # Try wildcard handler
        if "*" in self.event_handlers:
            try:
                self.event_handlers["*"](event)
                logger.debug(f"Dispatched event {event.event} to wildcard handler")
            except Exception as e:
                logger.error(f"Error in wildcard event handler: {str(e)}")
                raise
    
    @staticmethod
    def extract_event_data(event: WebhookEvent) -> Dict[str, Any]:
        """
        Extract relevant data from webhook event.
        
        Args:
            event: Webhook event
        
        Returns:
            Extracted data dictionary
        """
        data = event.data.copy()
        
        # Add common fields
        data["event_id"] = event.id
        data["event_type"] = event.event
        data["event_created_at"] = event.created_at
        
        return data
    
    @staticmethod
    def is_duplicate_event(
        event_id: str,
        processed_events: set,
        max_cache_size: int = 1000,
    ) -> bool:
        """
        Check if event is a duplicate (for idempotency).
        
        Args:
            event_id: Event ID to check
            processed_events: Set of processed event IDs
            max_cache_size: Maximum cache size before cleanup
        
        Returns:
            True if duplicate
        """
        if event_id in processed_events:
            logger.warning(f"Duplicate webhook event detected: {event_id}")
            return True
        
        # Add to processed set
        processed_events.add(event_id)
        
        # Clean up old events if cache is too large
        if len(processed_events) > max_cache_size:
            # Remove oldest events (convert to list, slice, convert back)
            events_list = list(processed_events)
            processed_events.clear()
            processed_events.update(events_list[-max_cache_size:])
        
        return False


class WebhookEventTypes:
    """Constants for webhook event types."""
    
    # Charge events
    CHARGE_CREATED = "charge.created"
    CHARGE_AUTHORIZED = "charge.authorized"
    CHARGE_CAPTURED = "charge.captured"
    CHARGE_FAILED = "charge.failed"
    CHARGE_REFUNDED = "charge.refunded"
    CHARGE_CANCELLED = "charge.cancelled"
    
    # Subscription events
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_SUSPENDED = "subscription.suspended"
    SUBSCRIPTION_RESUMED = "subscription.resumed"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_PAYMENT_SUCCEEDED = "subscription.payment.succeeded"
    SUBSCRIPTION_PAYMENT_FAILED = "subscription.payment.failed"
    
    # Token events
    TOKEN_CREATED = "token.created"
    TOKEN_USED = "token.used"
    TOKEN_EXPIRED = "token.expired"
    
    # Customer events
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    CUSTOMER_DELETED = "customer.deleted"
    
    # Refund events
    REFUND_CREATED = "refund.created"
    REFUND_UPDATED = "refund.updated"
    
    @classmethod
    def all_events(cls) -> list:
        """Get list of all event types."""
        return [
            value for name, value in vars(cls).items()
            if not name.startswith("_") and isinstance(value, str)
        ]


def create_webhook_response(success: bool = True, message: str = "OK") -> Dict[str, Any]:
    """
    Create a standard webhook response.
    
    Args:
        success: Whether webhook was processed successfully
        message: Response message
    
    Returns:
        Response dictionary
    """
    return {
        "success": success,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }