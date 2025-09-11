"""
Univapay Flask Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Flask integration for Univapay SDK.
"""

import json
import logging
from typing import Optional, Dict, Any, Callable
from functools import wraps

from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.exceptions import BadRequest

from ..client import UnivapayClient
from ..widget import UnivapayWidget
from ..webhook import WebhookHandler, create_webhook_response
from ..exceptions import UnivapayError, WebhookVerificationError


logger = logging.getLogger(__name__)


class UnivapayFlask:
    """Flask integration for Univapay SDK."""
    
    def __init__(self, app=None):
        """
        Initialize Flask integration.
        
        Args:
            app: Flask application instance (optional)
        """
        self.app = app
        self.client: Optional[UnivapayClient] = None
        self.widget: Optional[UnivapayWidget] = None
        self.webhook_handler: Optional[WebhookHandler] = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """
        Initialize with Flask app.
        
        Args:
            app: Flask application instance
        """
        # Get configuration
        app.config.setdefault("UNIVAPAY_APP_TOKEN", None)
        app.config.setdefault("UNIVAPAY_APP_SECRET", None)
        app.config.setdefault("UNIVAPAY_WEBHOOK_SECRET", None)
        app.config.setdefault("UNIVAPAY_ENDPOINT", None)
        app.config.setdefault("UNIVAPAY_TEST_MODE", app.debug)
        
        app_token = app.config["UNIVAPAY_APP_TOKEN"]
        app_secret = app.config["UNIVAPAY_APP_SECRET"]
        webhook_secret = app.config.get("UNIVAPAY_WEBHOOK_SECRET")
        endpoint = app.config.get("UNIVAPAY_ENDPOINT")
        test_mode = app.config.get("UNIVAPAY_TEST_MODE", False)
        
        if not app_token or not app_secret:
            app.logger.warning("Univapay credentials not configured")
            return
        
        # Initialize client
        self.client = UnivapayClient(
            app_token=app_token,
            app_secret=app_secret,
            endpoint=endpoint,
            test_mode=test_mode,
        )
        
        # Initialize widget
        self.widget = UnivapayWidget(
            app_token=app_token,
            test_mode=test_mode,
        )
        
        # Initialize webhook handler
        if webhook_secret:
            self.webhook_handler = WebhookHandler(webhook_secret)
        
        # Register extension with app
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["univapay"] = self
        
        # Add helper to g
        app.before_request(self._before_request)
    
    def _before_request(self):
        """Add univapay to Flask g object."""
        g.univapay = self
        g.univapay_client = self.client
        g.univapay_widget = self.widget
    
    def get_client(self) -> UnivapayClient:
        """Get Univapay client instance."""
        if not self.client:
            raise UnivapayError("Univapay client not initialized. Check your configuration.")
        return self.client
    
    def get_widget(self) -> UnivapayWidget:
        """Get Univapay widget instance."""
        if not self.widget:
            raise UnivapayError("Univapay widget not initialized. Check your configuration.")
        return self.widget
    
    def get_webhook_handler(self) -> WebhookHandler:
        """Get webhook handler instance."""
        if not self.webhook_handler:
            raise UnivapayError("Webhook handler not initialized. Set UNIVAPAY_WEBHOOK_SECRET.")
        return self.webhook_handler


def create_webhook_blueprint(
    univapay_instance: Optional[UnivapayFlask] = None,
    url_prefix: str = "/webhooks/univapay",
    endpoint: str = "webhook",
) -> Blueprint:
    """
    Create a Flask blueprint for webhook handling.
    
    Args:
        univapay_instance: UnivapayFlask instance (uses extension if not provided)
        url_prefix: URL prefix for the blueprint
        endpoint: Webhook endpoint path
    
    Returns:
        Flask Blueprint
    """
    bp = Blueprint("univapay_webhooks", __name__, url_prefix=url_prefix)
    
    @bp.route(f"/{endpoint.lstrip('/')}", methods=["POST"])
    def handle_webhook():
        """Handle Univapay webhook."""
        try:
            # Get Univapay instance
            if univapay_instance:
                univapay = univapay_instance
            elif "univapay" in current_app.extensions:
                univapay = current_app.extensions["univapay"]
            else:
                raise UnivapayError("Univapay not initialized")
            
            webhook_handler = univapay.get_webhook_handler()
            
            # Get request data
            payload = request.get_data(as_text=True)
            signature = request.headers.get("X-Signature")
            
            # Handle webhook
            event = webhook_handler.handle_webhook(
                payload=payload,
                signature=signature,
                headers=dict(request.headers),
            )
            
            # Log event
            current_app.logger.info(f"Received webhook event: {event.event} (ID: {event.id})")
            
            return jsonify(create_webhook_response(success=True)), 200
            
        except WebhookVerificationError as e:
            current_app.logger.error(f"Webhook verification failed: {str(e)}")
            return jsonify(create_webhook_response(success=False, message=str(e))), 400
            
        except Exception as e:
            current_app.logger.error(f"Webhook processing failed: {str(e)}")
            return jsonify(create_webhook_response(success=False, message="Internal error")), 500
    
    return bp


def requires_payment(amount: Optional[float] = None, currency: str = "JPY"):
    """
    Decorator to require payment for a route.
    
    Args:
        amount: Required payment amount
        currency: Payment currency
    
    Usage:
        @app.route("/premium")
        @requires_payment(amount=1000, currency="JPY")
        def premium_content():
            return "Premium content"
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if payment is verified (implement your logic)
            payment_token = request.args.get("payment_token") or request.form.get("payment_token")
            
            if not payment_token:
                return jsonify({"error": "Payment required"}), 402
            
            # Verify payment with Univapay (example)
            try:
                univapay = current_app.extensions.get("univapay")
                if not univapay:
                    raise UnivapayError("Univapay not initialized")
                
                # Add payment verification logic here
                # For example, verify the token or charge
                
                return f(*args, **kwargs)
                
            except UnivapayError as e:
                return jsonify({"error": str(e)}), 400
        
        return decorated_function
    return decorator


# Flask route helpers
class UnivapayRoutes:
    """Helper class for common Univapay routes."""
    
    @staticmethod
    def create_charge_route():
        """Create a charge from transaction token."""
        try:
            data = request.get_json()
            
            if not data:
                raise BadRequest("No JSON data provided")
            
            transaction_token_id = data.get("transaction_token_id")
            amount = data.get("amount")
            currency = data.get("currency", "JPY")
            
            if not transaction_token_id or not amount:
                raise BadRequest("Missing required fields")
            
            # Get client
            univapay = current_app.extensions.get("univapay")
            if not univapay:
                raise UnivapayError("Univapay not initialized")
            
            client = univapay.get_client()
            
            # Create charge
            charge = client.create_charge(
                transaction_token_id=transaction_token_id,
                amount=amount,
                currency=currency,
                capture=data.get("capture", True),
                metadata=data.get("metadata"),
            )
            
            return jsonify(charge.model_dump(by_alias=True)), 201
            
        except UnivapayError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Failed to create charge: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500
    
    @staticmethod
    def get_charge_route(charge_id: str):
        """Get charge details."""
        try:
            univapay = current_app.extensions.get("univapay")
            if not univapay:
                raise UnivapayError("Univapay not initialized")
            
            client = univapay.get_client()
            charge = client.get_charge(charge_id)
            
            return jsonify(charge.model_dump(by_alias=True)), 200
            
        except UnivapayError as e:
            return jsonify({"error": str(e)}), 400
    
    @staticmethod
    def refund_charge_route(charge_id: str):
        """Refund a charge."""
        try:
            data = request.get_json() or {}
            
            univapay = current_app.extensions.get("univapay")
            if not univapay:
                raise UnivapayError("Univapay not initialized")
            
            client = univapay.get_client()
            refund = client.refund_charge(
                charge_id=charge_id,
                amount=data.get("amount"),
                reason=data.get("reason"),
                metadata=data.get("metadata"),
            )
            
            return jsonify(refund), 200
            
        except UnivapayError as e:
            return jsonify({"error": str(e)}), 400
    
    @staticmethod
    def widget_config_route():
        """Get widget configuration."""
        try:
            univapay = current_app.extensions.get("univapay")
            if not univapay:
                raise UnivapayError("Univapay not initialized")
            
            widget = univapay.get_widget()
            
            # Get parameters from request
            params = request.args.to_dict()
            
            config = widget.get_widget_config(
                checkout_type=params.get("checkout_type", "payment"),
                amount=params.get("amount"),
                currency=params.get("currency", "JPY"),
                metadata=params.get("metadata"),
            )
            
            return jsonify(config), 200
            
        except UnivapayError as e:
            return jsonify({"error": str(e)}), 400


def register_univapay_routes(app, url_prefix: str = "/api/univapay"):
    """
    Register standard Univapay routes with Flask app.
    
    Args:
        app: Flask application
        url_prefix: URL prefix for routes
    """
    # Create charge
    app.add_url_rule(
        f"{url_prefix}/charges",
        "univapay_create_charge",
        UnivapayRoutes.create_charge_route,
        methods=["POST"],
    )
    
    # Get charge
    app.add_url_rule(
        f"{url_prefix}/charges/<charge_id>",
        "univapay_get_charge",
        UnivapayRoutes.get_charge_route,
        methods=["GET"],
    )
    
    # Refund charge
    app.add_url_rule(
        f"{url_prefix}/charges/<charge_id>/refund",
        "univapay_refund_charge",
        UnivapayRoutes.refund_charge_route,
        methods=["POST"],
    )
    
    # Widget config
    app.add_url_rule(
        f"{url_prefix}/widget/config",
        "univapay_widget_config",
        UnivapayRoutes.widget_config_route,
        methods=["GET"],
    )


# Context processor for templates
def univapay_context_processor():
    """Add Univapay to template context."""
    univapay = current_app.extensions.get("univapay")
    if univapay:
        return {
            "univapay_widget": univapay.widget,
            "univapay_widget_url": univapay.widget.get_widget_url() if univapay.widget else None,
        }
    return {}