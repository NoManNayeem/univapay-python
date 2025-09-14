from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import SubscriptionsAPI
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Fetch a subscription by id")
    add_common_args(ap)
    ap.add_argument("--id", required=True, help="Subscription id")
    ap.add_argument("--wait", action="store_true", help="Wait for a terminal-ish status (server polling)")
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        api = SubscriptionsAPI(client)
        try:
            sub = api.get(args.id)
            print("[SUB] Current:")
            print(pretty(sub.model_dump(mode="json")))
            print(f"[SUB] status={sub.status}")
            if args.wait:
                print("[SUB] Waiting for terminal-ish status...")
                sub = api.wait_until_terminal(args.id, server_polling=True, timeout_s=120, interval_s=3.0)
            print("[SUB] Final:")
            print(pretty(sub.model_dump(mode="json")))
            print(f"[SUB] final status={sub.status}")
            print("\n[SUB] OK ✅")
        except UnivapayHTTPError as e:
            print(f"[SUB] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
