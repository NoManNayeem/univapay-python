from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import SubscriptionsAPI
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Cancel a subscription")
    add_common_args(ap)
    ap.add_argument("--id", required=True, help="Subscription id")
    ap.add_argument(
        "--termination-mode",
        choices=["immediate", "on_next_payment"],
        default=None,
        help="If POST /cancel is unavailable, fallback PATCH uses this mode (default immediate)",
    )
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        api = SubscriptionsAPI(client)
        try:
            resp = api.cancel(args.id, termination_mode=args.termination_mode)
            # Try to fetch latest state with polling
            try:
                resp = api.get(args.id, polling=True)
            except Exception:
                pass
            from univapay.models import Subscription
            if isinstance(resp, Subscription):
                print(pretty(resp.model_dump(mode="json")))
            else:
                print(pretty(resp))
        except UnivapayHTTPError as e:
            print(f"[SUB CANCEL] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
