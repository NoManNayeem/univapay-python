"""
Univapay SDK Widget
~~~~~~~~~~~~~~~~~~~

Widget helper utilities for frontend integration.
"""

import json
from typing import Optional, Dict, Any, Union
from decimal import Decimal
from enum import Enum

from .models import CheckoutType, TokenType, Currency
from .exceptions import ValidationError


class WidgetTheme(str, Enum):
    """Widget theme options."""
    DEFAULT = "default"
    DARK = "dark"
    LIGHT = "light"
    MINIMAL = "minimal"


class UnivapayWidget:
    """Helper class for Univapay widget integration."""
    
    WIDGET_URL = "https://widget.univapay.com/client/checkout.js"
    
    def __init__(
        self,
        app_token: str,
        test_mode: bool = False,
    ):
        """
        Initialize widget helper.
        
        Args:
            app_token: Univapay application token (store token for frontend)
            test_mode: Use test widget if True
        """
        if not app_token:
            raise ValidationError("app_token is required for widget")
        
        self.app_token = app_token
        self.test_mode = test_mode
    
    def render_html(
        self,
        checkout_type: Union[str, CheckoutType] = CheckoutType.PAYMENT,
        amount: Optional[Union[int, Decimal]] = None,
        currency: Optional[Union[str, Currency]] = None,
        button_text: Optional[str] = None,
        css_class: Optional[str] = None,
        theme: Optional[Union[str, WidgetTheme]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Generate HTML for declarative widget setup.
        
        Args:
            checkout_type: Type of checkout (payment, token, subscription)
            amount: Payment amount
            currency: Currency code
            button_text: Custom button text
            css_class: CSS class for the widget container
            theme: Widget theme
            metadata: Additional metadata
            **kwargs: Additional data attributes
        
        Returns:
            HTML string for widget
        """
        # Build data attributes
        data_attrs = {
            "data-app-id": self.app_token,
            "data-checkout": str(checkout_type).lower(),
        }
        
        if amount is not None:
            data_attrs["data-amount"] = str(int(amount))
        
        if currency:
            data_attrs["data-currency"] = str(currency).lower()
        
        if button_text:
            data_attrs["data-txt"] = button_text
        
        if theme:
            data_attrs["data-theme"] = str(theme)
        
        if metadata:
            data_attrs["data-metadata"] = json.dumps(metadata)
        
        # Add any additional kwargs as data attributes
        for key, value in kwargs.items():
            attr_name = f"data-{key.replace('_', '-')}"
            if isinstance(value, bool):
                data_attrs[attr_name] = "true" if value else "false"
            elif value is not None:
                data_attrs[attr_name] = str(value)
        
        # Build HTML
        attrs_str = " ".join(f'{k}="{v}"' for k, v in data_attrs.items())
        
        if css_class:
            attrs_str += f' class="{css_class}"'
        
        html = f"""
<script src="{self.WIDGET_URL}"></script>
<span {attrs_str}></span>
"""
        
        return html.strip()
    
    def render_javascript(
        self,
        checkout_type: Union[str, CheckoutType] = CheckoutType.PAYMENT,
        amount: Optional[Union[int, Decimal]] = None,
        currency: Optional[Union[str, Currency]] = None,
        token_type: Optional[Union[str, TokenType]] = None,
        cvv_authorize: bool = False,
        button_selector: Optional[str] = None,
        opened_callback: Optional[str] = None,
        success_callback: Optional[str] = None,
        error_callback: Optional[str] = None,
        token_created_callback: Optional[str] = None,
        subscription_created_callback: Optional[str] = None,
        closed_callback: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Generate JavaScript for programmatic widget setup.
        
        Args:
            checkout_type: Type of checkout
            amount: Payment amount
            currency: Currency code
            token_type: Token type for token checkout
            cvv_authorize: Require CVV authorization
            button_selector: CSS selector for trigger button
            opened_callback: JavaScript function name for opened event
            success_callback: JavaScript function name for success event
            error_callback: JavaScript function name for error event
            token_created_callback: JavaScript function name for token created event
            subscription_created_callback: JavaScript function name for subscription created
            closed_callback: JavaScript function name for closed event
            metadata: Additional metadata
            **kwargs: Additional configuration options
        
        Returns:
            JavaScript code string
        """
        # Build configuration object
        config = {
            "appId": self.app_token,
            "checkout": str(checkout_type).lower(),
        }
        
        if amount is not None:
            config["amount"] = int(amount)
        
        if currency:
            config["currency"] = str(currency).lower()
        
        if token_type:
            config["tokenType"] = str(token_type)
        
        if cvv_authorize:
            config["cvvAuthorize"] = True
        
        if metadata:
            config["metadata"] = metadata
        
        # Add callbacks if provided
        callbacks = []
        
        if opened_callback:
            callbacks.append(f"opened: {opened_callback}")
        
        if success_callback:
            callbacks.append(f"onSuccess: {success_callback}")
        
        if error_callback:
            callbacks.append(f"onError: {error_callback}")
        
        if token_created_callback:
            callbacks.append(f"onTokenCreated: {token_created_callback}")
        
        if subscription_created_callback:
            callbacks.append(f"onSubscriptionCreated: {subscription_created_callback}")
        
        if closed_callback:
            callbacks.append(f"closed: {closed_callback}")
        
        # Add additional options
        for key, value in kwargs.items():
            if value is not None:
                if isinstance(value, bool):
                    config[key] = value
                elif isinstance(value, (int, float, Decimal)):
                    config[key] = float(value)
                else:
                    config[key] = str(value)
        
        # Generate JavaScript
        config_str = json.dumps(config, indent=2)
        
        # Insert callbacks into config string (they need to be functions, not strings)
        if callbacks:
            callbacks_str = ",\n  ".join(callbacks)
            # Insert callbacks before the closing brace
            config_str = config_str[:-1] + ",\n  " + callbacks_str + "\n}"
        
        js_code = f"""
<script src="{self.WIDGET_URL}"></script>
<script>
  var univapayCheckout = UnivapayCheckout.create({config_str});
"""
        
        if button_selector:
            js_code += f"""
  
  document.querySelector("{button_selector}").onclick = function() {{
    univapayCheckout.open();
  }};
"""
        
        js_code += """
</script>
"""
        
        return js_code.strip()
    
    def get_widget_config(
        self,
        checkout_type: Union[str, CheckoutType] = CheckoutType.PAYMENT,
        amount: Optional[Union[int, Decimal]] = None,
        currency: Optional[Union[str, Currency]] = None,
        token_type: Optional[Union[str, TokenType]] = None,
        cvv_authorize: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Get widget configuration as a dictionary.
        
        This can be used for custom implementations or 
        passing to frontend frameworks.
        
        Args:
            checkout_type: Type of checkout
            amount: Payment amount
            currency: Currency code
            token_type: Token type for token checkout
            cvv_authorize: Require CVV authorization
            metadata: Additional metadata
            **kwargs: Additional configuration options
        
        Returns:
            Configuration dictionary
        """
        config = {
            "appId": self.app_token,
            "checkout": str(checkout_type).lower(),
        }
        
        if amount is not None:
            config["amount"] = int(amount)
        
        if currency:
            config["currency"] = str(currency).lower()
        
        if token_type:
            config["tokenType"] = str(token_type)
        
        if cvv_authorize:
            config["cvvAuthorize"] = True
        
        if metadata:
            config["metadata"] = metadata
        
        # Add additional options
        for key, value in kwargs.items():
            if value is not None:
                if isinstance(value, bool):
                    config[key] = value
                elif isinstance(value, (int, float, Decimal)):
                    config[key] = float(value)
                else:
                    config[key] = str(value)
        
        return config
    
    def get_widget_url(self) -> str:
        """
        Get the widget script URL.
        
        Returns:
            Widget script URL
        """
        return self.WIDGET_URL
    
    def generate_event_listeners(self) -> str:
        """
        Generate JavaScript for window event listeners.
        
        Returns:
            JavaScript code for event listeners
        """
        return """
<script>
  // Univapay widget event listeners
  window.addEventListener("univapay:success", function(event) {
    console.log("Payment successful:", event.detail);
    // Handle success - e.g., redirect to success page
  });
  
  window.addEventListener("univapay:error", function(event) {
    console.error("Payment error:", event.detail);
    // Handle error - e.g., show error message
  });
  
  window.addEventListener("univapay:token:created", function(event) {
    console.log("Token created:", event.detail);
    // Handle token creation - e.g., send to backend
  });
  
  window.addEventListener("univapay:subscription:created", function(event) {
    console.log("Subscription created:", event.detail);
    // Handle subscription creation
  });
  
  window.addEventListener("univapay:closed", function(event) {
    console.log("Widget closed");
    // Handle widget close
  });
</script>
"""
    
    def validate_amount(self, amount: Union[int, float, Decimal], currency: str) -> bool:
        """
        Validate amount for a given currency.
        
        Args:
            amount: Payment amount
            currency: Currency code
        
        Returns:
            True if valid
        
        Raises:
            ValidationError: If amount is invalid
        """
        if amount <= 0:
            raise ValidationError("Amount must be greater than 0")
        
        # Check minimum amounts for different currencies
        min_amounts = {
            "JPY": 50,  # 50 yen minimum
            "USD": 0.50,  # 50 cents minimum
            "EUR": 0.50,
            "GBP": 0.30,
        }
        
        min_amount = min_amounts.get(currency.upper(), 0.01)
        
        if float(amount) < min_amount:
            raise ValidationError(
                f"Amount must be at least {min_amount} {currency}"
            )
        
        return True