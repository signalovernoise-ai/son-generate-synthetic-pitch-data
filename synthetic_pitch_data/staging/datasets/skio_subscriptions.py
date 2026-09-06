"""Stage cleaner for Skio subscriptions. Reusable across all Skio clients.

One row per subscribed line. Two shape differences from Recharge are normalized here so
downstream churn work does not need to know which platform a client runs:

- ids are UUID strings rather than integers (left as strings — do not coerce to numeric);
- enums arrive UPPER_SNAKE (`ACTIVE`, `TOO_EXPENSIVE`) and are lowercased to the shared
  vocabulary.

`cancelled_at` records when the customer acted in the portal, which is not necessarily when
billing stopped — the churn-dating caveat is raised in the notes rather than silently
"fixed", because only the billing-attempt stream can settle it.
"""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="skio_subscriptions.csv",
    role="subscriptions",
    source_files=["skio_subscriptions.csv"],
    key="id",
    required=["id", "shopify_customer_id", "created_at"],
    timestamp_cols=["created_at", "updated_at", "cancelled_at", "paused_at", "next_billing_date"],
    reversal_pairs=[("created_at", "updated_at"), ("created_at", "cancelled_at")],
    primary_timestamp="created_at",
    upper_cols=["presentment_currency"],
    lower_enum_cols=[
        "status",
        "cancellation_reason",
        "billing_interval_unit",
        "delivery_interval_unit",
    ],
    fks=[("shopify_customer_id", "customers", "id")],
    provides_keys=["id"],
    static_notes=[
        "cancelled_at is the portal action, not the billing stop. Date churn from the last "
        "SUCCEEDED billing attempt in skio_subscription_orders where the two disagree.",
        "Subscriptions created before the extract window are retained: a subscription that was "
        "already running is not an error, and dropping them would understate tenure.",
        "cancellation_reason is blank on a large share of cancellations — Skio's flow lets the "
        "customer skip it. Blank means 'not given', not 'no reason'; do not impute.",
        "billing_interval_count and delivery_interval_count are equal except on prepaid plans. "
        "The interval mix drives the retention curve's shape: a 3-month plan cannot renew at m1.",
    ],
)
