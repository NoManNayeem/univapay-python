from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import ChargesAPI
from univapay.utils import ensure_idempotency_key, make_idempotency_key
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Create a one-time charge")
    add_common_args(ap)
    ap.add_argument("--token", required=True, help="Transaction token id (one-time)")
    ap.add_argument("--amount", required=True, type=int, help="Amount in minor units (e.g., JPY)")
    ap.add_argument("--currency", default="jpy", help="Currency (default jpy)")
    ap.add_argument("--capture", action="store_true", help="Capture immediately (default True)")
    ap.add_argument("--no-capture", action="store_true", help="If set, do NOT capture immediately")
    ap.add_argument("--idempotency-key", default=None, help="Optional Idempotency-Key")
    ap.add_argument("--wait", action="store_true", help="Wait until terminal status")
    args = ap.parse_args()

    capture = True
    if args.no_capture:
        capture = False
    elif args.capture:
        capture = True

    idem = ensure_idempotency_key(args.idempotency_key, prefix="one_time")
    print("[RUN] Creating charge")
    print(f"  token     : {args.token}")
    print(f"  amount    : {args.amount}")
    print(f"  currency  : {args.currency}")
    print(f"  capture   : {capture}")
    print(f"  idem-key  : {idem}")

    client = make_client_from_args(args)
    try:
        api = ChargesAPI(client)
        try:
            ch = api.create_one_time(
                token_id=args.token,
                amount=args.amount,
                currency=args.currency,
                capture=capture,
                idempotency_key=idem,
            )
            if args.wait:
                ch = api.wait_until_terminal(ch.id, server_polling=True, timeout_s=120, interval_s=3.0)
            print(pretty(ch.model_dump(mode="json")))
        except UnivapayHTTPError as e:
            print(f"[RUN] HTTP ERROR ❌ status={e.status} req_id={e.request_id}")
            print(f"[RUN] payload: {pretty(e.payload)}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
