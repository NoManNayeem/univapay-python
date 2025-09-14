from __future__ import annotations
import argparse, json
from _common import add_common_args, make_client_from_args, pretty
from univapay.debug import dprint

def main():
    ap = argparse.ArgumentParser(description="Quick GET charges?limit=1 smoke test")
    add_common_args(ap)
    args = ap.parse_args()

    client = make_client_from_args(args)
    try:
        path = client._path("charges")
        print("[SMOKE] GET", f"{path}?limit=1")
        data = client.get(path, params={"limit": 1})
        print(pretty(data)[:1000] + "..." if len(pretty(data)) > 1000 else pretty(data))
        print("\n[SMOKE] OK ✅")
    finally:
        client.close()

if __name__ == "__main__":
    main()
