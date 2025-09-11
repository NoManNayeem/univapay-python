"""
Univapay Django Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Django and Django REST Framework integration for Univapay SDK.
"""

import json
import logging
from typing import Optional, Dict, Any, Type
from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import models, transaction

from ..client import UnivapayClient
from ..widget import UnivapayWidget
from ..webhook import WebhookHandler, create_webhook_response
from ..exceptions import UnivapayError, WebhookVerificationError


logger = logging.getLogger(__name__)


class UnivapayDjango:
    """Django integration for Univapay SDK."""
    
    def __init__(self, app=None):
        """
        Initialize Django integration.
        
        Args:
            app: Django settings module (optional)
        """
        self.client: Optional[UnivapayClient] = None
        self.widget: Optional[UnivapayWidget] = None
        self.webhook_handler: Optional[WebhookHandler] = None
        
        if app:
            self.init_app(app)
        else:
            self.init_from_settings()
    
    def init_app(self, app):
        """Initialize with Django app settings."""
        self.init_from_settings()
    
    def init_from_settings(self):
        """Initialize from Django settings."""
        # Get settings with defaults
        app_token = getattr(settings, "UNIVAPAY_APP_TOKEN", None)
        app_secret = getattr(settings, "UNIVAPAY_APP_SECRET", None)
        webhook_secret = getattr(settings, "UNIVAPAY_WEBHOOK_SECRET", None)
        endpoint = getattr(settings, "UNIVAPAY_ENDPOINT", None)
        test_mode = getattr(settings, "UNIVAPAY_TEST_MODE", settings.DEBUG)
        
        if app_token and app_secret:
            self.client = UnivapayClient(
                app_token=app_token,
                app_secret=app_secret,
                endpoint=endpoint,
                test_mode=test_mode,
            )
            
            # Initialize widget (uses app_token only)
            self.widget = UnivapayWidget(
                app_token=app_token,
                test_mode=test_mode,
            )
        
        if webhook_secret:
            self.webhook_handler = WebhookHandler(webhook_secret)
    
    def get_client(self) -> UnivapayClient:
        """Get Univapay client instance."""
        if not self.client:
            raise UnivapayError("Univapay client not initialized. Check your settings.")
        return self.client
    
    def get_widget(self) -> UnivapayWidget:
        """Get Univapay widget instance."""
        if not self.widget:
            raise UnivapayError("Univapay widget not initialized. Check your settings.")
        return self.widget
    
    def get_webhook_handler(self) -> WebhookHandler:
        """Get webhook handler instance."""
        if not self.webhook_handler:
            raise UnivapayError("Webhook handler not initialized. Set UNIVAPAY_WEBHOOK_SECRET.")
        return self.webhook_handler


# Global instance
univapay = UnivapayDjango()


@method_decorator(csrf_exempt, name="dispatch")
class DjangoWebhookView(View):
    """Django view for handling Univapay webhooks."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.webhook_handler = univapay.get_webhook_handler()
    
    def post(self, request: HttpRequest) -> JsonResponse:
        """
        Handle webhook POST request.
        
        Args:
            request: Django HTTP request
        
        Returns:
            JSON response
        """
        try:
            # Get raw body
            payload = request.body.decode("utf-8")
            
            # Get signature from headers
            signature = request.headers.get("X-Signature")
            
            # Handle webhook
            event = self.webhook_handler.handle_webhook(
                payload=payload,
                signature=signature,
                headers=dict(request.headers),
            )
            
            # Process event (override this method in subclass)
            self.process_event(event)
            
            return JsonResponse(create_webhook_response(success=True))
            
        except WebhookVerificationError as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JsonResponse(
                create_webhook_response(success=False, message=str(e)),
                status=400,
            )
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return JsonResponse(
                create_webhook_response(success=False, message="Internal error"),
                status=500,
            )
    
    def process_event(self, event):
        """
        Process webhook event. Override this in subclass.
        
        Args:
            event: Webhook event object
        """
        logger.info(f"Received webhook event: {event.event} (ID: {event.id})")


# Django REST Framework support
try:
    from rest_framework import serializers, views, status
    from rest_framework.response import Response
    
    class ChargeSerializer(serializers.Serializer):
        """DRF serializer for charge creation."""
        transaction_token_id = serializers.CharField()
        amount = serializers.DecimalField(max_digits=10, decimal_places=2)
        currency = serializers.CharField(max_length=3)
        capture = serializers.BooleanField(default=True, required=False)
        metadata = serializers.DictField(required=False)
    
    class RefundSerializer(serializers.Serializer):
        """DRF serializer for refund creation."""
        charge_id = serializers.CharField()
        amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
        reason = serializers.CharField(required=False)
        metadata = serializers.DictField(required=False)
    
    class DRFWebhookView(views.APIView):
        """Django REST Framework view for webhooks."""
        
        authentication_classes = []  # No authentication for webhooks
        permission_classes = []  # No permissions for webhooks
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.webhook_handler = univapay.get_webhook_handler()
        
        def post(self, request):
            """Handle webhook POST request."""
            try:
                # Get raw body or JSON data
                if hasattr(request, "body"):
                    payload = request.body.decode("utf-8")
                else:
                    payload = request.data
                
                # Get signature
                signature = request.headers.get("X-Signature")
                
                # Handle webhook
                event = self.webhook_handler.handle_webhook(
                    payload=payload,
                    signature=signature,
                    headers=dict(request.headers),
                )
                
                # Process event
                self.process_event(event)
                
                return Response(
                    create_webhook_response(success=True),
                    status=status.HTTP_200_OK,
                )
                
            except WebhookVerificationError as e:
                return Response(
                    create_webhook_response(success=False, message=str(e)),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.error(f"Webhook processing failed: {str(e)}")
                return Response(
                    create_webhook_response(success=False, message="Internal error"),
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        
        def process_event(self, event):
            """Process webhook event. Override in subclass."""
            logger.info(f"Received webhook event: {event.event}")
    
    class ChargeAPIView(views.APIView):
        """DRF view for creating charges."""
        
        def post(self, request):
            """Create a charge."""
            serializer = ChargeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            try:
                client = univapay.get_client()
                charge = client.create_charge(**serializer.validated_data)
                
                return Response(
                    charge.model_dump(by_alias=True),
                    status=status.HTTP_201_CREATED,
                )
            except UnivapayError as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
    
except ImportError:
    # DRF not installed
    pass


# Django Models
class UnivapayPaymentMixin(models.Model):
    """Mixin for Django models to add Univapay payment fields."""
    
    univapay_charge_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Univapay charge ID",
    )
    univapay_transaction_token_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Univapay transaction token ID",
    )
    univapay_status = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Payment status from Univapay",
    )
    univapay_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Payment amount",
    )
    univapay_currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
        help_text="Payment currency",
    )
    univapay_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional payment metadata",
    )
    univapay_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was created at Univapay",
    )
    univapay_captured_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was captured",
    )
    
    class Meta:
        abstract = True
    
    def create_charge(self, amount: Decimal, currency: str, **kwargs) -> Any:
        """
        Create a charge for this model instance.
        
        Args:
            amount: Charge amount
            currency: Currency code
            **kwargs: Additional charge parameters
        
        Returns:
            Charge object
        """
        client = univapay.get_client()
        
        # Add model reference to metadata
        metadata = kwargs.get("metadata", {})
        metadata.update({
            "model": self.__class__.__name__,
            "model_id": str(self.pk),
        })
        kwargs["metadata"] = metadata
        
        # Create charge
        charge = client.create_charge(
            transaction_token_id=self.univapay_transaction_token_id,
            amount=amount,
            currency=currency,
            **kwargs,
        )
        
        # Update model fields
        self.univapay_charge_id = charge.id
        self.univapay_status = charge.status
        self.univapay_amount = charge.amount
        self.univapay_currency = charge.currency
        self.univapay_created_at = charge.created_at
        
        if charge.captured:
            self.univapay_captured_at = charge.updated_at
        
        self.save(update_fields=[
            "univapay_charge_id",
            "univapay_status",
            "univapay_amount",
            "univapay_currency",
            "univapay_created_at",
            "univapay_captured_at",
        ])
        
        return charge
    
    def get_charge(self) -> Optional[Any]:
        """Get charge details from Univapay."""
        if not self.univapay_charge_id:
            return None
        
        client = univapay.get_client()
        return client.get_charge(self.univapay_charge_id)
    
    def refund_charge(self, amount: Optional[Decimal] = None, reason: Optional[str] = None) -> Any:
        """
        Refund the charge.
        
        Args:
            amount: Refund amount (None for full refund)
            reason: Refund reason
        
        Returns:
            Refund response
        """
        if not self.univapay_charge_id:
            raise ValueError("No charge ID available")
        
        client = univapay.get_client()
        refund = client.refund_charge(
            charge_id=self.univapay_charge_id,
            amount=amount,
            reason=reason,
        )
        
        # Update status
        self.univapay_status = "refunded"
        self.save(update_fields=["univapay_status"])
        
        return refund


class UnivapaySubscriptionMixin(models.Model):
    """Mixin for Django models to add Univapay subscription fields."""
    
    univapay_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Univapay subscription ID",
    )
    univapay_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Univapay customer ID",
    )
    univapay_subscription_status = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Subscription status",
    )
    univapay_next_billing_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next billing date",
    )
    
    class Meta:
        abstract = True
    
    def create_subscription(self, **kwargs) -> Any:
        """Create a subscription for this model instance."""
        client = univapay.get_client()
        subscription = client.create_subscription(**kwargs)
        
        self.univapay_subscription_id = subscription.id
        self.univapay_subscription_status = subscription.status
        self.univapay_next_billing_date = subscription.next_billing_date
        self.save()
        
        return subscription