from __future__ import annotations
import os, json
from univapay.widgets import (
    build_one_time_widget_config,
    build_subscription_widget_config,
    build_recurring_widget_config,
    to_json as widget_to_json,
)
from univapay.debug import dprint

def main():
    # Ensure UNIVAPAY_JWT is set in your environment before running.
    jwt = os.getenv("UNIVAPAY_JWT")
    if not jwt:
        print("UNIVAPAY_JWT is not set; export it before running this example.")
        return

    one_time = build_one_time_widget_config(
        amount=12000,
        form_id="form-one-time-alpha",
        button_id="btn-one-time-alpha",
        description="Product Alpha - One-time payment",
        payment_methods={
            "card": True,
            "online": {
                "pay_pay_online": False,
                "alipay_online": False,
                "alipay_plus_online": False,
                "we_chat_online": False,
                "d_barai_online": False,
            },
            "konbini": {},
            "bank_transfer": {},
        },
    )

    subscription = build_subscription_widget_config(
        amount=59400,
        period="semiannually",
        form_id="form-subscription-semiannual",
        button_id="btn-subscription-semiannual",
        description="6 Months Subscription",
        payment_methods={"card": True},
    )

    recurring = build_recurring_widget_config(
        amount=30000,
        form_id="form-installments",
        button_id="btn-installments",
        description="Recurring Billing",
        payment_methods={"card": True},
    )

    print("ONE-TIME JSON:")
    print(widget_to_json(one_time, pretty=True))
    print("\nSUBSCRIPTION JSON:")
    print(widget_to_json(subscription, pretty=True))
    print("\nRECURRING JSON:")
    print(widget_to_json(recurring, pretty=True))

if __name__ == "__main__":
    main()
