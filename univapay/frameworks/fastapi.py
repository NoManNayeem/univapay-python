"""
Univapay FastAPI Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

FastAPI integration for Univapay SDK.
"""

import logging
from typing import Optional, Dict, Any, Callable, List
from decimal import Decimal

from fastapi import APIRouter, Request, Response, HTTPException, Depends, Header, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..client import UnivapayClient
from ..widget import UnivapayWidget
from ..webhook import WebhookHandler, create_webhook_response
from ..exceptions import UnivapayError, WebhookVerificationError
from ..models import Currency, PaymentStatus


logger = logging.getLogger(__name__)


class UnivapayFastAPI:
    """FastAPI integration for Univapay SDK."""
    
    def __init__(
        self,
        app_token: Optional[str] = None,
        app_secret: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        endpoint: Optional[str] = None,
        test_mode: bool = False,
    ):
        """
        Initialize FastAPI integration.
        
        Args:
            app_token: Univapay application token
            app_secret: Univapay application secret
            webhook_secret: Webhook secret for signature verification
            endpoint: API endpoint URL
            test_mode: Use test mode
        """
        self.client: Optional[UnivapayClient] = None
        self.widget: Optional[UnivapayWidget] = None
        self.webhook_handler: Optional[WebhookHandler] = None
        
        if app_token and app_secret:
            self.client = UnivapayClient(
                app_token=app_token,
                app_secret=app_secret,
                endpoint=endpoint,
                test_mode=test_mode,
            )
            
            self.widget = UnivapayWidget(
                app_token=app_token,
                test_mode=test_mode,
            )
        
        if webhook_secret:
            self.webhook_handler = WebhookHandler(webhook_secret)
    
    def get_client(self) -> UnivapayClient:
        """Get Univapay client instance."""
        if not self.client:
            raise UnivapayError("Univapay client not initialized")
        return self.client
    
    def get_widget(self) -> UnivapayWidget:
        """Get Univapay widget instance."""
        if not self.widget:
            raise UnivapayError("Univapay widget not initialized")
        return self.widget
    
    def get_webhook_handler(self) -> WebhookHandler:
        """Get webhook handler instance."""
        if not self.webhook_handler:
            raise UnivapayError("Webhook handler not initialized")
        return self.webhook_handler


# Pydantic models for request/response
class CreateChargeRequest(BaseModel):
    """Request model for creating a charge."""
    transaction_token_id: str = Field(..., description="Transaction token ID")
    amount: Decimal = Field(..., description="Charge amount", gt=0)
    currency: Currency = Field(..., description="Currency code")
    capture: bool = Field(True, description="Auto-capture the charge")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RefundRequest(BaseModel):
    """Request model for creating a refund."""
    amount: Optional[Decimal] = Field(None, description="Refund amount (None for full refund)")
    reason: Optional[str] = Field(None, description="Refund reason")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChargeResponse(BaseModel):
    """Response model for charge."""
    id: str
    transaction_token_id: str = Field(alias="transactionTokenId")
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    captured: bool
    created_at: str = Field(alias="createdAt")


class WidgetConfigRequest(BaseModel):
    """Request model for widget configuration."""
    checkout_type: str = Field("payment", description="Checkout type")
    amount: Optional[int] = Field(None, description="Payment amount")
    currency: Optional[str] = Field("JPY", description="Currency code")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Dependency injection
def get_univapay(request: Request) -> UnivapayFastAPI:
    """
    Dependency to get Univapay instance.
    
    This should be configured in your FastAPI app startup.
    """
    if not hasattr(request.app.state, "univapay"):
        raise HTTPException(status_code=500, detail="Univapay not configured")
    return request.app.state.univapay


def create_webhook_router(
    univapay_instance: Optional[UnivapayFastAPI] = None,
    prefix: str = "/webhooks",
    tags: List[str] = ["webhooks"],
) -> APIRouter:
    """
    Create a FastAPI router for webhook handling.
    
    Args:
        univapay_instance: UnivapayFastAPI instance
        prefix: Router prefix
        tags: Router tags
    
    Returns:
        FastAPI APIRouter
    """
    router = APIRouter(prefix=prefix, tags=tags)
    
    @router.post("/univapay")
    async def handle_webhook(
        request: Request,
        x_signature: Optional[str] = Header(None),
    ):
        """Handle Univapay webhook."""
        try:
            # Get Univapay instance
            if univapay_instance:
                univapay = univapay_instance
            else:
                univapay = request.app.state.univapay
            
            webhook_handler = univapay.get_webhook_handler()
            
            # Get request body
            body = await request.body()
            payload = body.decode("utf-8")
            
            # Handle webhook
            event = webhook_handler.handle_webhook(
                payload=payload,
                signature=x_signature,
                headers=dict(request.headers),
            )
            
            logger.info(f"Received webhook event: {event.event} (ID: {event.id})")
            
            return JSONResponse(
                content=create_webhook_response(success=True),
                status_code=200,
            )
            
        except WebhookVerificationError as e:
            logger.error(f"Webhook verification failed: {str(e)}")
            return JSONResponse(
                content=create_webhook_response(success=False, message=str(e)),
                status_code=400,
            )
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}")
            return JSONResponse(
                content=create_webhook_response(success=False, message="Internal error"),
                status_code=500,
            )
    
    return router


def create_payment_router(
    univapay_instance: Optional[UnivapayFastAPI] = None,
    prefix: str = "/api/payments",
    tags: List[str] = ["payments"],
) -> APIRouter:
    """
    Create a FastAPI router for payment operations.
    
    Args:
        univapay_instance: UnivapayFastAPI instance
        prefix: Router prefix
        tags: Router tags
    
    Returns:
        FastAPI APIRouter
    """
    router = APIRouter(prefix=prefix, tags=tags)
    
    @router.post("/charges", response_model=ChargeResponse)
    async def create_charge(
        charge_request: CreateChargeRequest,
        univapay: UnivapayFastAPI = Depends(get_univapay),
    ):
        """Create a new charge."""
        try:
            client = univapay.get_client()
            charge = client.create_charge(
                transaction_token_id=charge_request.transaction_token_id,
                amount=charge_request.amount,
                currency=charge_request.currency.value,
                capture=charge_request.capture,
                metadata=charge_request.metadata,
            )
            
            return ChargeResponse(
                id=charge.id,
                transaction_token_id=charge.transaction_token_id,
                amount=charge.amount,
                currency=charge.currency,
                status=charge.status,
                captured=charge.captured,
                created_at=charge.created_at.isoformat(),
            )
            
        except UnivapayError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.get("/charges/{charge_id}")
    async def get_charge(
        charge_id: str,
        univapay: UnivapayFastAPI = Depends(get_univapay),
    ):
        """Get charge details."""
        try:
            client = univapay.get_client()
            charge = client.get_charge(charge_id)
            return charge.model_dump(by_alias=True)
            
        except UnivapayError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.post("/charges/{charge_id}/capture")
    async def capture_charge(
        charge_id: str,
        amount: Optional[Decimal] = Body(None),
        univapay: UnivapayFastAPI = Depends(get_univapay),
    ):
        """Capture an authorized charge."""
        try:
            client = univapay.get_client()
            charge = client.capture_charge(charge_id, amount)
            return charge.model_dump(by_alias=True)
            
        except UnivapayError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.post("/charges/{charge_id}/refund")
    async def refund_charge(
        charge_id: str,
        refund_request: RefundRequest,
        univapay: UnivapayFastAPI = Depends(get_univapay),
    ):
        """Refund a charge."""
        try:
            client = univapay.get_client()
            refund = client.refund_charge(
                charge_id=charge_id,
                amount=refund_request.amount,
                reason=refund_request.reason,
                metadata=refund_request.metadata,
            )
            return refund
            
        except UnivapayError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @router.get("/widget/config")
    async def get_widget_config(
        config_request: WidgetConfigRequest = Depends(),
        univapay: UnivapayFastAPI = Depends(get_univapay),
    ):
        """Get widget configuration."""
        try:
            widget = univapay.get_widget()
            config = widget.get_widget_config(
                checkout_type=config_request.checkout_type,
                amount=config_request.amount,
                currency=config_request.currency,
                metadata=config_request.metadata,
            )
            return config
            
        except UnivapayError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    return router


# Middleware for payment verification
class PaymentRequiredMiddleware:
    """Middleware to require payment for certain routes."""
    
    def __init__(
        self,
        app,
        univapay: UnivapayFastAPI,
        protected_paths: List[str],
        amount: Optional[Decimal] = None,
        currency: str = "JPY",
    ):
        """
        Initialize payment middleware.
        
        Args:
            app: FastAPI application
            univapay: UnivapayFastAPI instance
            protected_paths: List of paths requiring payment
            amount: Required payment amount
            currency: Payment currency
        """
        self.app = app
        self.univapay = univapay
        self.protected_paths = protected_paths
        self.amount = amount
        self.currency = currency
    
    async def __call__(self, request: Request, call_next):
        """Process request."""
        # Check if path requires payment
        if any(request.url.path.startswith(path) for path in self.protected_paths):
            # Check for payment token
            payment_token = request.query_params.get("payment_token")
            
            if not payment_token:
                return JSONResponse(
                    content={"error": "Payment required"},
                    status_code=402,
                )
            
            # Verify payment (implement your logic)
            try:
                # Example: verify token with Univapay
                client = self.univapay.get_client()
                # Add verification logic here
                
            except UnivapayError:
                return JSONResponse(
                    content={"error": "Invalid payment"},
                    status_code=402,
                )
        
        response = await call_next(request)
        return response


# Helper functions for FastAPI app setup
def setup_univapay(
    app,
    app_token: str,
    app_secret: str,
    webhook_secret: Optional[str] = None,
    test_mode: bool = False,
    include_routers: bool = True,
):
    """
    Setup Univapay integration with FastAPI app.
    
    Args:
        app: FastAPI application instance
        app_token: Univapay application token
        app_secret: Univapay application secret
        webhook_secret: Webhook secret
        test_mode: Use test mode
        include_routers: Include default routers
    """
    # Initialize Univapay
    univapay = UnivapayFastAPI(
        app_token=app_token,
        app_secret=app_secret,
        webhook_secret=webhook_secret,
        test_mode=test_mode,
    )
    
    # Store in app state
    app.state.univapay = univapay
    
    # Include routers if requested
    if include_routers:
        # Add payment router
        payment_router = create_payment_router(univapay)
        app.include_router(payment_router)
        
        # Add webhook router if webhook secret is provided
        if webhook_secret:
            webhook_router = create_webhook_router(univapay)
            app.include_router(webhook_router)
    
    return univapay


# Dependency for protected routes
async def require_payment(
    request: Request,
    payment_token: Optional[str] = None,
    univapay: UnivapayFastAPI = Depends(get_univapay),
):
    """
    Dependency to require payment for a route.
    
    Usage:
        @app.get("/premium", dependencies=[Depends(require_payment)])
        async def premium_content():
            return {"content": "Premium content"}
    """
    if not payment_token:
        raise HTTPException(status_code=402, detail="Payment required")
    
    # Verify payment token (implement your logic)
    try:
        client = univapay.get_client()
        # Add verification logic here
        
    except UnivapayError as e:
        raise HTTPException(status_code=402, detail=f"Invalid payment: {str(e)}")
    
    return True