from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import RefundsAPI
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="List refunds for a charge")
    add_common_args(ap)
    ap.add_argument("--charge-id", required=True, help="Charge id")
    ap.add_argument("--limit", type=int, default=None, help="Limit page size")
    ap.add_argument("--cursor", default=None, help="Next cursor")
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        api = RefundsAPI(client)
        try:
            resp = api.list(args.charge_id, limit=args.limit, cursor=args.cursor)
            print(pretty(resp))
        except UnivapayHTTPError as e:
            print(f"[REFUND LIST] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
