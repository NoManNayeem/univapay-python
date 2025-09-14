from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Optional, Dict, Any

# Try to load .env if python-dotenv is available (safe if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Error types
from .errors import UnivapayConfigError


# ----------------------------- helpers -----------------------------

def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    return v not in ("0", "false", "no", "off", "")


def _parse_float(value: Optional[str], default: float) -> float:
    try:
        return float(value) if value is not None else default
    except Exception:
        return default


def _parse_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


def _normalize_base_url(url: Optional[str]) -> str:
    url = (url or "").strip()
    if not url:
        return "https://api.univapay.com"
    # Remove trailing slash to avoid double slashes when building paths
    return url[:-1] if url.endswith("/") else url


def _mask(token: Optional[str], kind: str) -> str:
    """Mask sensitive values for debug printing."""
    if not token:
        return "(empty)"
    if kind == "secret":
        # Show only first 2 chars if any
        return token[:2] + "***"
    if kind == "jwt":
        # JWT-like string; show small head/tail
        t = token.strip()
        if len(t) <= 10:
            return "***"
        return t[:6] + "..." + t[-4:]
    return "***"


def _dprint(enabled: bool, *args: Any) -> None:
    if enabled:
        # Keep the same style you've been using everywhere
        print("[UnivapaySDK][Config]", *args)


# ----------------------------- config -----------------------------

@dataclass
class UnivapayConfig:
    """
    Configuration with precedence:
      explicit kwargs > environment (.env) > defaults

    Server-side calls require BOTH jwt and secret.
    """

    # Credentials
    jwt: Optional[str] = None
    secret: Optional[str] = None

    # Routing / network
    store_id: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[float] = None

    # Diagnostics
    debug: Optional[bool] = None

    # Optional retry hints (client may use these; also available via env)
    # UNIVAPAY_RETRIES, UNIVAPAY_BACKOFF
    retries: Optional[int] = None
    backoff_factor: Optional[float] = None

    # Internal: where each field was sourced from (arg/env/default) for debugging
    _source: Dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        env = os.environ

        # jwt
        if self.jwt is None or self.jwt == "":
            self.jwt = env.get("UNIVAPAY_JWT", "")
            self._source["jwt"] = "env"
        else:
            self._source["jwt"] = "arg"

        # secret
        if self.secret is None or self.secret == "":
            self.secret = env.get("UNIVAPAY_SECRET", "")
            self._source["secret"] = "env"
        else:
            self._source["secret"] = "arg"

        # store_id
        if self.store_id is None or self.store_id == "":
            self.store_id = env.get("UNIVAPAY_STORE_ID") or None
            self._source["store_id"] = "env"
        else:
            self._source["store_id"] = "arg"

        # base_url
        if self.base_url is None or self.base_url == "":
            self.base_url = _normalize_base_url(env.get("UNIVAPAY_BASE_URL"))
            self._source["base_url"] = "env/default"
        else:
            self.base_url = _normalize_base_url(self.base_url)
            self._source["base_url"] = "arg"

        # timeout
        if self.timeout is None:
            self.timeout = _parse_float(env.get("UNIVAPAY_TIMEOUT"), 30.0)
            self._source["timeout"] = "env/default"
        else:
            try:
                self.timeout = float(self.timeout)
            except Exception:
                self.timeout = 30.0
            self._source["timeout"] = "arg"

        # debug
        if self.debug is None:
            self.debug = _parse_bool(env.get("UNIVAPAY_DEBUG", "1"), True)
            self._source["debug"] = "env/default"
        else:
            self.debug = bool(self.debug)
            self._source["debug"] = "arg"

        # optional retry hints
        if self.retries is None:
            self.retries = _parse_int(env.get("UNIVAPAY_RETRIES"), 0)
            self._source["retries"] = "env/default"
        else:
            try:
                self.retries = int(self.retries)
            except Exception:
                self.retries = 0
            self._source["retries"] = "arg"

        if self.backoff_factor is None:
            self.backoff_factor = _parse_float(env.get("UNIVAPAY_BACKOFF"), 0.5)
            self._source["backoff_factor"] = "env/default"
        else:
            try:
                self.backoff_factor = float(self.backoff_factor)
            except Exception:
                self.backoff_factor = 0.5
            self._source["backoff_factor"] = "arg"

        # Initial debug print (sanitized)
        _dprint(
            bool(self.debug),
            "Loaded config:",
            {
                "jwt": _mask(self.jwt, "jwt"),
                "secret": _mask(self.secret, "secret"),
                "store_id": self.store_id or None,
                "base_url": self.base_url,
                "timeout": self.timeout,
                "debug": self.debug,
                "source": self._source,
            },
        )

    # -------- validation & utils --------
    def validate(self) -> "UnivapayConfig":
        """
        Validate presence of credentials for server-side API calls.
        (Widget-only use-cases can bypass by not instantiating this config.)
        """
        if not self.jwt or not self.secret:
            _dprint(
                bool(self.debug),
                "Validation failed: jwt/secret missing",
                {"jwt": _mask(self.jwt, "jwt"), "secret": _mask(self.secret, "secret")},
            )
            raise UnivapayConfigError(
                "UNIVAPAY_JWT and UNIVAPAY_SECRET are required for server-side API calls."
            )
        _dprint(bool(self.debug), "Validation OK")
        return self

    def require_store_id(self) -> str:
        """Ensure a store_id is present for endpoints that need it."""
        if not self.store_id:
            raise UnivapayConfigError("UNIVAPAY_STORE_ID is required for this operation.")
        return self.store_id

    def masked(self) -> dict:
        """Return a sanitized dict for logging/diagnostics."""
        return {
            "jwt": _mask(self.jwt, "jwt"),
            "secret": _mask(self.secret, "secret"),
            "store_id": self.store_id,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "debug": self.debug,
            "retries": self.retries,
            "backoff_factor": self.backoff_factor,
        }

    def copy_with(
        self,
        *,
        jwt: Optional[str] = None,
        secret: Optional[str] = None,
        store_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        debug: Optional[bool] = None,
        retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
    ) -> "UnivapayConfig":
        """Create a modified copy (handy in tests)."""
        return replace(
            self,
            jwt=self.jwt if jwt is None else jwt,
            secret=self.secret if secret is None else secret,
            store_id=self.store_id if store_id is None else store_id,
            base_url=_normalize_base_url(base_url if base_url is not None else self.base_url),
            timeout=self.timeout if timeout is None else float(timeout),
            debug=self.debug if debug is None else bool(debug),
            retries=self.retries if retries is None else int(retries),
            backoff_factor=self.backoff_factor if backoff_factor is None else float(backoff_factor),
        )

    # -------- alt constructors --------
    @classmethod
    def from_env(cls) -> "UnivapayConfig":
        """Build config strictly from environment (.env considered if loaded)."""
        return cls().validate()


__all__ = ["UnivapayConfig"]
