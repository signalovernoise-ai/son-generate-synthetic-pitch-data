"""Stage cleaner for Shopify orders. Reusable across all Shopify clients.

Canonical commerce-order table after cleaning. Derives net_sale_price (refund-netted).
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec


def add_net_sale_price(df: pd.DataFrame, report) -> pd.DataFrame:
    total = pd.to_numeric(df.get("total_price"), errors="coerce")
    refunded = pd.to_numeric(df.get("refunded_amount"), errors="coerce")
    if refunded is None:
        refunded = pd.Series(0.0, index=df.index)
    refunded = refunded.fillna(0.0)
    df["net_sale_price"] = (total - refunded).clip(lower=0).round(2)
    netted = int((refunded > 0).sum())
    report.record(
        "refund_netting", netted, "derived",
        "net_sale_price = total_price - refunded_amount (full refunds net to 0)",
    )
    report.note(
        "net_sale_price nets refunded_amount off total_price. Where a source exposes refund "
        "status but no amount, the gross value is retained and flagged here."
    )
    return df


SPEC = DatasetSpec(
    name="shopify_orders.csv",
    role="orders",
    source_files=["shopify_orders.csv"],
    key="id",
    display_id_col="name",
    required=["id", "customer_id", "created_at", "total_price"],
    timestamp_cols=["created_at", "processed_at", "updated_at"],
    reversal_pairs=[("created_at", "processed_at"), ("created_at", "updated_at")],
    primary_timestamp="created_at",
    amount_col="total_price",
    amount_bounds=(0.5, 5000.0),
    email_cols=["email"],
    country_cols=["billing_address_country_code"],
    upper_cols=["currency", "presentment_currency"],
    lower_enum_cols=["financial_status", "fulfillment_status", "refund_status"],
    test_pattern_cols=["email", "source_name"],
    status_col="financial_status",
    keep_statuses={"paid", "refunded", "partially_refunded"},
    near_dup_group=["customer_id"],
    fks=[("customer_id", "customers", "id")],
    provides_keys=["id"],
    post_hooks=[add_net_sale_price],
)
