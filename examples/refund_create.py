from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import RefundsAPI
from univapay.utils import ensure_idempotency_key
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Create a refund for a charge")
    add_common_args(ap)
    ap.add_argument("--charge-id", required=True, help="Charge id")
    ap.add_argument("--amount", type=int, default=None, help="Amount in minor units (omit for full refund if allowed)")
    ap.add_argument("--reason", default=None, help="Optional reason")
    ap.add_argument("--currency", default=None, help="Optional currency (required by some accounts for partial refunds)")
    ap.add_argument("--idempotency-key", default=None, help="Optional Idempotency-Key")
    args = ap.parse_args()

    idem = ensure_idempotency_key(args.idempotency_key, prefix="refund")
    client = make_client_from_args(args)
    try:
        api = RefundsAPI(client)
        try:
            extra = {}
            if args.currency:
                extra["currency"] = args.currency.upper()
            rf = api.create(args.charge_id, amount=args.amount, reason=args.reason, idempotency_key=idem, **extra)
            print(pretty(rf.model_dump(mode="json")))
        except UnivapayHTTPError as e:
            print(f"[REFUND] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
