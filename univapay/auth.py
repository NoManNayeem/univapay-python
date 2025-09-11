"""
Univapay SDK Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~

JWT authentication handling for Univapay API.
"""

import time
import json
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .exceptions import AuthenticationError, ConfigurationError


class JWTAuth:
    """JWT authentication handler for Univapay API."""
    
    def __init__(self, app_token: str, app_secret: str):
        """
        Initialize JWT authentication.
        
        Args:
            app_token: Univapay application token
            app_secret: Univapay application secret
        """
        if not app_token or not app_secret:
            raise ConfigurationError("Both app_token and app_secret are required")
        
        self.app_token = app_token
        self.app_secret = app_secret
        self._token_cache: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
    
    def get_authorization_header(self) -> str:
        """
        Get the authorization header value.
        
        Returns:
            Authorization header value in format: Bearer {secret}.{token}
        """
        return f"Bearer {self.app_secret}.{self.app_token}"
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get complete headers for API requests.
        
        Returns:
            Dictionary of headers including authorization and content-type
        """
        return {
            "Authorization": self.get_authorization_header(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Univapay-Python-SDK/0.1.0",
        }
    
    def create_jwt_token(self, payload: Dict[str, Any], expires_in: int = 300) -> str:
        """
        Create a JWT token for specific operations.
        
        Args:
            payload: Token payload data
            expires_in: Token expiry time in seconds (default: 5 minutes)
        
        Returns:
            JWT token string
        """
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }
        
        # Add expiration to payload
        payload["exp"] = int(time.time()) + expires_in
        payload["iat"] = int(time.time())
        
        # Encode header and payload
        header_encoded = self._base64_url_encode(json.dumps(header))
        payload_encoded = self._base64_url_encode(json.dumps(payload))
        
        # Create signature (simplified - in production, use proper HMAC-SHA256)
        message = f"{header_encoded}.{payload_encoded}"
        
        # For now, return unsigned token (implement HMAC-SHA256 if needed)
        return f"{message}.{self.app_secret}"
    
    def decode_jwt_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise AuthenticationError("Invalid token format")
            
            # Decode payload
            payload = json.loads(self._base64_url_decode(parts[1]))
            
            # Check expiration
            if "exp" in payload and payload["exp"] < time.time():
                raise AuthenticationError("Token has expired")
            
            return payload
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise AuthenticationError(f"Failed to decode token: {str(e)}")
    
    def _base64_url_encode(self, data: str) -> str:
        """
        Base64 URL-safe encoding.
        
        Args:
            data: String to encode
        
        Returns:
            Base64 URL-encoded string
        """
        encoded = base64.urlsafe_b64encode(data.encode()).decode()
        # Remove padding
        return encoded.rstrip("=")
    
    def _base64_url_decode(self, data: str) -> str:
        """
        Base64 URL-safe decoding.
        
        Args:
            data: Base64 URL-encoded string
        
        Returns:
            Decoded string
        """
        # Add padding if needed
        padding = 4 - (len(data) % 4)
        if padding != 4:
            data += "=" * padding
        
        decoded = base64.urlsafe_b64decode(data).decode()
        return decoded
    
    def validate_credentials(self) -> bool:
        """
        Validate that credentials are properly formatted.
        
        Returns:
            True if credentials are valid
        """
        # Check token format (basic validation)
        if not self.app_token or len(self.app_token) < 10:
            return False
        
        if not self.app_secret or len(self.app_secret) < 10:
            return False
        
        # Check for valid characters
        import re
        token_pattern = re.compile(r'^[A-Za-z0-9_\-]+$')
        
        if not token_pattern.match(self.app_token):
            return False
        
        if not token_pattern.match(self.app_secret):
            return False
        
        return True
    
    def is_store_token(self) -> bool:
        """
        Check if the token is a store-type token (for frontend use).
        
        Returns:
            True if store token, False if merchant token
        """
        # Store tokens typically start with "st_" or have specific patterns
        return self.app_token.startswith("st_") or "store" in self.app_token.lower()
    
    def is_test_mode(self) -> bool:
        """
        Check if using test credentials.
        
        Returns:
            True if test mode
        """
        return "test" in self.app_token.lower() or "test" in self.app_secret.lower()