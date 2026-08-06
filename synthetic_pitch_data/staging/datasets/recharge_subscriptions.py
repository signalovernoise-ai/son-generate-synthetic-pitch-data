"""Stage cleaner for Recharge subscriptions. Reusable across all Recharge clients.

One row per subscribed line. `cancelled_at` records when the customer acted in the
portal, which is not necessarily when billing stopped — the churn-dating caveat is
raised in the notes rather than silently "fixed", because only the charge stream can
settle it.
"""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="recharge_subscriptions.csv",
    role="subscriptions",
    source_files=["recharge_subscriptions.csv"],
    key="id",
    required=["id", "shopify_customer_id", "created_at"],
    timestamp_cols=["created_at", "updated_at", "cancelled_at", "next_charge_scheduled_at"],
    reversal_pairs=[("created_at", "updated_at"), ("created_at", "cancelled_at")],
    primary_timestamp="created_at",
    upper_cols=["presentment_currency"],
    lower_enum_cols=["status", "order_interval_unit", "cancellation_reason"],
    fks=[("shopify_customer_id", "customers", "id")],
    provides_keys=["id"],
    static_notes=[
        "cancelled_at is the portal action, not the billing stop. Date churn from the last "
        "successful charge in recharge_subscription_orders where the two disagree.",
        "Subscriptions created before the extract window are retained: a subscription that was "
        "already running is not an error, and dropping them would understate tenure.",
    ],
)
