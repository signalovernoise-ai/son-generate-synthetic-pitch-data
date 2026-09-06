"""Stage cleaner for Recharge charges. Reusable across all Recharge clients.

The charge stream is the bridge between subscription state and commerce: a successful
charge creates a real Shopify order. Failed and skipped charges legitimately have no
`shopify_order_id`, so that FK is sparse rather than broken and blank values are left
alone by the orphan check.

Non-final charge statuses (error/queued/skipped) are removed from the staged table so
downstream revenue work counts billing once; the count is reported in the notes so the
dunning volume is not lost.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec


def flag_dunning_retries(df: pd.DataFrame, report) -> pd.DataFrame:
    """Charges tried more than once are dunning retries — the usual origin of
    duplicate-looking orders in a subscription store."""
    tried = pd.to_numeric(df.get("number_times_tried"), errors="coerce")
    if tried is None:
        return df
    retried = int((tried > 1).sum())
    if retried:
        report.record(
            "dunning_retry", retried, "flagged",
            "number_times_tried > 1 (retained; expect duplicate-looking commerce orders nearby)",
        )
    return df


SPEC = DatasetSpec(
    name="recharge_subscription_orders.csv",
    role="subscription_orders",
    source_files=["recharge_subscription_orders.csv"],
    key="id",
    required=["id", "subscription_id", "created_at"],
    timestamp_cols=["scheduled_at", "processed_at", "created_at", "updated_at", "retry_date"],
    reversal_pairs=[("scheduled_at", "processed_at"), ("created_at", "updated_at")],
    primary_timestamp="created_at",
    amount_col="total_price",
    amount_bounds=(0.0, 5000.0),
    upper_cols=["currency"],
    lower_enum_cols=["type", "status", "tags"],
    status_col="status",
    keep_statuses={"success"},
    fks=[
        ("shopify_order_id", "orders", "id"),
        ("shopify_customer_id", "customers", "id"),
        ("subscription_id", "subscriptions", "id"),
    ],
    provides_keys=["id"],
    pre_hooks=[flag_dunning_retries],
    static_notes=[
        "type separates the subscription's first order (checkout) from renewals (recurring). "
        "Use it rather than re-deriving first-vs-repeat from order dates.",
        "shipping_price is carried separately and stays out of AOV, per metric-definitions.md.",
    ],
)
