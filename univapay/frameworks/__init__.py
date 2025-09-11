"""
Univapay Framework Integrations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Framework-specific integrations for Django, Flask, and FastAPI.
"""

import importlib
from typing import Optional, Any


def get_framework_integration(framework: str) -> Optional[Any]:
    """
    Dynamically load framework integration.
    
    Args:
        framework: Framework name (django, flask, fastapi)
    
    Returns:
        Framework integration module or None
    """
    framework_modules = {
        "django": ".django",
        "flask": ".flask",
        "fastapi": ".fastapi",
    }
    
    module_path = framework_modules.get(framework.lower())
    if not module_path:
        return None
    
    try:
        return importlib.import_module(module_path, package="univapay.frameworks")
    except ImportError:
        return None


# Try to auto-detect and import available frameworks
try:
    from .django import UnivapayDjango, DjangoWebhookView
    __all__ = ["UnivapayDjango", "DjangoWebhookView"]
except ImportError:
    pass

try:
    from .flask import UnivapayFlask, create_webhook_blueprint
    if "UnivapayFlask" not in locals().get("__all__", []):
        __all__ = __all__ + ["UnivapayFlask", "create_webhook_blueprint"] if "__all__" in locals() else ["UnivapayFlask", "create_webhook_blueprint"]
except ImportError:
    pass

try:
    from .fastapi import UnivapayFastAPI, create_webhook_router
    if "UnivapayFastAPI" not in locals().get("__all__", []):
        __all__ = __all__ + ["UnivapayFastAPI", "create_webhook_router"] if "__all__" in locals() else ["UnivapayFastAPI", "create_webhook_router"]
except ImportError:
    pass