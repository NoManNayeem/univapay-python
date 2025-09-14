from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import ChargesAPI
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Capture a previously authorized charge")
    add_common_args(ap)
    ap.add_argument("--id", required=True, help="Charge id")
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        api = ChargesAPI(client)
        try:
            ch = api.capture(args.id)
            print(pretty(ch.model_dump(mode='json')))
        except UnivapayHTTPError as e:
            print(f"[CAPTURE] HTTP {e.status} req_id={e.request_id}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
