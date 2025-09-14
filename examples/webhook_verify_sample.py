from __future__ import annotations
import argparse, json, sys
from univapay.resources.webhooks import verify_and_parse, WebhookVerificationError


def main():
    ap = argparse.ArgumentParser(
        description="Verify a webhook signature & parse payload (offline sample)"
    )
    ap.add_argument("--secret", required=True, help="Webhook signing secret")
    ap.add_argument("--header", required=True, help="Signature header value (e.g., sha256=...)")
    ap.add_argument("--header-name", default=None, help="Header name override (default auto-detect)")
    ap.add_argument("--file", required=True, help="Path to JSON body file to verify/parse")
    args = ap.parse_args()

    # Read body and construct minimal headers map for verification
    with open(args.file, "rb") as f:
        body = f.read()
    headers = {(args.header_name or "X-Univapay-Signature"): args.header}

    try:
        info, ev = verify_and_parse(
            body=body,
            headers=headers,
            secret=args.secret,
            header_name=args.header_name,
        )
        print(json.dumps(ev.model_dump(mode="json"), ensure_ascii=False, indent=2))
        print("\n[WEBHOOK] OK ✅", "(header:", info.get("header"), ")")
    except WebhookVerificationError as e:
        print("[WEBHOOK] Verification failed:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()

