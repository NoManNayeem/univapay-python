from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import httpx

from .config import UnivapayConfig
from .debug import dprint, djson, scrub_headers
from .errors import UnivapayHTTPError  # unified error type

try:
    # __version__ is defined in univapay/__init__.py
    from . import __version__ as SDK_VERSION  # type: ignore
except Exception:
    SDK_VERSION = "0.0.0"


# -------------------- constants --------------------

RATE_HEADERS: Tuple[str, ...] = (
    "X-Remaining-Requests-Exact",
    "X-Remaining-Requests-Route",
    "X-Requests-Per-Minute-Exact",
    "X-Requests-Per-Minute-Route",
)

# Treat as transient for simple retry/backoff
TRANSIENT_STATUS: Tuple[int, ...] = (429, 500, 502, 503, 504)

REQUEST_ID_HEADERS: Tuple[str, ...] = ("X-Request-ID", "X-Request-Id")


def _auth_header(secret: str, jwt: str) -> str:
    # Bearer {secret}.{jwt}
    return f"Bearer {secret}.{jwt}"


def _first_header(headers: httpx.Headers, names: Tuple[str, ...]) -> Optional[str]:
    for n in names:
        v = headers.get(n)
        if v:
            return v
    return None


class UnivapayClient:
    """
    Lightweight sync client for Univapay REST.

    - Adds Authorization header "Bearer {secret}.{jwt}".
    - Supports Idempotency-Key on mutating requests.
    - Optional simple retries/backoff for transient errors (429/5xx).
    - Prints sanitized debug logs (Authorization redacted).
    """

    def __init__(
        self,
        config: UnivapayConfig,
        *,
        retries: int = 0,
        backoff_factor: float = 0.5,
    ):
        self.config = config.validate()
        self.retries = max(0, int(retries))
        self.backoff_factor = max(0.0, float(backoff_factor))

        self._client = httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={
                "User-Agent": f"univapay-python/{SDK_VERSION}",
            },
        )
        dprint(
            "Client init",
            {
                "base_url": self.config.base_url,
                "store_id": self.config.store_id,
                "timeout": self.config.timeout,
                "debug": self.config.debug,
                "retries": self.retries,
                "backoff_factor": self.backoff_factor,
                "sdk_version": SDK_VERSION,
            },
        )

    # ------------ context manager support ------------
    def __enter__(self) -> "UnivapayClient":
        dprint("__enter__()")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        dprint("__exit__() -> close()")
        self.close()

    # ------------ internal helpers ------------
    def _headers(
        self,
        *,
        idempotency_key: Optional[str] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        h: Dict[str, str] = {
            "Authorization": _auth_header(self.config.secret, self.config.jwt),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        if extra:
            h.update(extra)
        djson("Request headers", scrub_headers(h))
        return h

    def _extract_meta(self, r: httpx.Response) -> Dict[str, Any]:
        meta: Dict[str, Any] = {k: r.headers.get(k) for k in RATE_HEADERS if k in r.headers}
        req_id = _first_header(r.headers, REQUEST_ID_HEADERS)
        if req_id:
            meta["request_id"] = req_id
        retry_after = r.headers.get("Retry-After")
        if retry_after:
            meta["retry_after"] = retry_after
        return meta

    def _handle(self, r: httpx.Response) -> Dict[str, Any]:
        meta = self._extract_meta(r)
        dprint("Response", {"status": r.status_code, "request_id": meta.get("request_id")})
        if meta:
            dprint("Rate limits", {k: v for k, v in meta.items() if k in RATE_HEADERS})

        # Parse body safely
        if r.status_code == 204 or not r.content:
            body: Dict[str, Any] = {}
        else:
            try:
                body = r.json()
                if not isinstance(body, dict):
                    body = {"data": body}
            except Exception:
                body = {"message": r.text}

        djson("Response body", body)

        if 200 <= r.status_code < 300:
            body.setdefault("_meta", {})["rate_limits"] = {k: v for k, v in meta.items() if k in RATE_HEADERS}
            if meta.get("request_id"):
                body["_meta"]["request_id"] = meta["request_id"]
            if meta.get("retry_after"):
                body["_meta"]["retry_after"] = meta["retry_after"]
            return body

        # Error path
        raise UnivapayHTTPError(r.status_code, body, meta.get("request_id"))

    def _path(self, resource: str) -> str:
        p = f"/stores/{self.config.store_id}/{resource}" if self.config.store_id else f"/{resource}"
        dprint("Resolved path", p)
        return p

    def _sleep_for_retry(self, attempt: int, *, retry_after_header: Optional[str]) -> float:
        # Use Retry-After if present (seconds). Fallback to exponential backoff.
        if retry_after_header:
            try:
                # Header may be seconds or HTTP-date; we only support seconds here.
                secs = float(retry_after_header)
                if secs >= 0:
                    return secs
            except Exception:
                pass
        return self.backoff_factor * (2 ** attempt)

    def _send_with_retries(self, method: str, url: str, **kwargs) -> httpx.Response:
        attempt = 0
        while True:
            try:
                dprint("HTTP send", {"method": method.upper(), "url": url})
                r = self._client.request(method, url, **kwargs)
                if r.status_code in TRANSIENT_STATUS and attempt < self.retries:
                    wait = self._sleep_for_retry(attempt, retry_after_header=r.headers.get("Retry-After"))
                    dprint(
                        "Transient response -> retry",
                        {"status": r.status_code, "attempt": attempt + 1, "sleep": wait},
                    )
                    time.sleep(max(0.0, wait))
                    attempt += 1
                    continue
                return r
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.HTTPError) as e:
                if attempt < self.retries:
                    wait = self.backoff_factor * (2 ** attempt)
                    dprint(
                        "Network error -> retry",
                        {"error": repr(e), "attempt": attempt + 1, "sleep": wait},
                    )
                    time.sleep(max(0.0, wait))
                    attempt += 1
                    continue
                dprint("Network error -> giving up", {"error": repr(e)})
                raise UnivapayHTTPError(-1, {"message": str(e)}, None) from e

    # ------------ public request helpers ------------
    def get(
        self,
        resource_path: str,
        *,
        polling: bool = False,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        params = dict(params or {})
        if polling:
            params["polling"] = "true"
        dprint("GET", {"path": resource_path, "params": params})
        r = self._send_with_retries(
            "GET",
            resource_path,
            params=params,
            headers=self._headers(extra=extra_headers),
        )
        return self._handle(r)

    def post(
        self,
        resource_path: str,
        *,
        json: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        dprint("POST", {"path": resource_path})
        djson("Request JSON", json)
        r = self._send_with_retries(
            "POST",
            resource_path,
            json=json,
            params=params,
            headers=self._headers(idempotency_key=idempotency_key, extra=extra_headers),
        )
        return self._handle(r)

    def patch(
        self,
        resource_path: str,
        *,
        json: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        dprint("PATCH", {"path": resource_path})
        djson("Request JSON", json)
        r = self._send_with_retries(
            "PATCH",
            resource_path,
            json=json,
            params=params,
            headers=self._headers(idempotency_key=idempotency_key, extra=extra_headers),
        )
        return self._handle(r)

    def put(
        self,
        resource_path: str,
        *,
        json: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        dprint("PUT", {"path": resource_path})
        djson("Request JSON", json)
        r = self._send_with_retries(
            "PUT",
            resource_path,
            json=json,
            params=params,
            headers=self._headers(idempotency_key=idempotency_key, extra=extra_headers),
        )
        return self._handle(r)

    def delete(
        self,
        resource_path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        dprint("DELETE", {"path": resource_path})
        if json is not None:
            djson("Request JSON", json)
        r = self._send_with_retries(
            "DELETE",
            resource_path,
            json=json,
            params=params,
            headers=self._headers(idempotency_key=idempotency_key, extra=extra_headers),
        )
        return self._handle(r)

    def head(
        self,
        resource_path: str,
        *,
        params: Dict[str, Any] | None = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        dprint("HEAD", {"path": resource_path, "params": params or {}})
        r = self._send_with_retries(
            "HEAD",
            resource_path,
            params=params or {},
            headers=self._headers(extra=extra_headers),
        )
        # HEAD returns no body; expose meta only
        meta = self._extract_meta(r)
        return {"_meta": {"rate_limits": {k: v for k, v in meta.items() if k in RATE_HEADERS},
                          "request_id": meta.get("request_id"),
                          "retry_after": meta.get("retry_after")}}

    def close(self) -> None:
        dprint("Client close()")
        self._client.close()
