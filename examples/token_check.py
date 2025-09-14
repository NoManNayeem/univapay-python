from __future__ import annotations
import argparse
from _common import add_common_args, make_client_from_args, pretty
from univapay.resources import TokensAPI
from univapay.errors import UnivapayHTTPError

def main():
    ap = argparse.ArgumentParser(description="Fetch a transaction token by id")
    add_common_args(ap)
    ap.add_argument("--token", required=True, help="Transaction token id")
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        api = TokensAPI(client)
        try:
            tok = api.get(args.token)
            print(pretty(tok.model_dump(mode="json")))
        except UnivapayHTTPError as e:
            print(f"[TOKEN] HTTP {e.status}")
            print(pretty(e.payload))
    finally:
        client.close()

if __name__ == "__main__":
    main()
