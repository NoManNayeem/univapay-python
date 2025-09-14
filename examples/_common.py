from __future__ import annotations
import argparse, json, sys
from typing import Optional, Dict, Any
from univapay import UnivapayConfig, UnivapayClient
from univapay.debug import dprint, djson

def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base-url", default=None, help="Override UNIVAPAY_BASE_URL")
    p.add_argument("--store-id", default=None, help="Override UNIVAPAY_STORE_ID")
    p.add_argument("--jwt", default=None, help="Override UNIVAPAY_JWT")
    p.add_argument("--secret", default=None, help="Override UNIVAPAY_SECRET")
    p.add_argument("--timeout", type=float, default=None, help="HTTP timeout seconds")
    p.add_argument("--debug", type=int, default=None, help="Set debug 1/0 (overrides UNIVAPAY_DEBUG)")

def make_client_from_args(args) -> UnivapayClient:
    cfg = UnivapayConfig(
        jwt=args.jwt,
        secret=args.secret,
        store_id=args.store_id,
        base_url=args.base_url,
        timeout=args.timeout,
        debug=(None if args.debug is None else bool(args.debug)),
    )
    dprint("[COMMON] Config", cfg.masked())
    cfg.validate()
    client = UnivapayClient(cfg, retries=1, backoff_factor=0.5)
    return client

def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
