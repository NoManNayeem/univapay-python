from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import SubscriptionsAPI
from univapay.utils import ensure_idempotency_key
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Create a subscription from a subscription token")
    add_common_args(ap)
    ap.add_argument("--token", required=True, help="Transaction token id (subscription)")
    ap.add_argument("--amount", required=True, type=int, help="Amount in minor units")
    ap.add_argument(
        "--period",
        required=True,
        choices=[
            "daily","weekly","biweekly","monthly","bimonthly","quarterly","semiannually","annually","yearly"
        ],
        help="Billing interval (supports: daily, weekly, biweekly, monthly, bimonthly, quarterly, semiannually, annually/yearly)",
    )
    ap.add_argument("--currency", default="jpy", help="Currency (default jpy)")
    ap.add_argument("--start-on", default=None, help="Optional start date (YYYY-MM-DD)")
    ap.add_argument("--idempotency-key", default=None, help="Optional Idempotency-Key")
    ap.add_argument("--wait", action="store_true", help="Wait for terminal-ish status")
    args = ap.parse_args()

    idem = ensure_idempotency_key(args.idempotency_key, prefix="subscription")
    client = make_client_from_args(args)
    try:
        api = SubscriptionsAPI(client)
        try:
            sub = api.create(
                token_id=args.token,
                amount=args.amount,
                period=args.period,
                currency=args.currency,
                start_on=args.start_on,
                idempotency_key=idem,
            )
            if args.wait:
                sub = api.wait_until_terminal(sub.id, server_polling=True, timeout_s=120, interval_s=3.0)
            print(pretty(sub.model_dump(mode="json")))
        except UnivapayHTTPError as e:
            print(f"[SUB CREATE] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
