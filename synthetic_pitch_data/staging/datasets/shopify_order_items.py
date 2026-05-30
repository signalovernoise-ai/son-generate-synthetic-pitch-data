"""Stage cleaner for Shopify order line items. Reusable across all Shopify clients.

Derives is_subscription from selling-plan presence (the documented Shopify signal),
rather than inferring subscriptions from discounted pricing.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec


def add_is_subscription(df: pd.DataFrame, report) -> pd.DataFrame:
    sp = df.get("selling_plan_id")
    if sp is None:
        flag = pd.Series(False, index=df.index)
    else:
        sp = sp.astype("string").str.strip()
        flag = sp.notna() & (sp != "")
    df["is_subscription"] = flag
    report.record(
        "subscription_flag", int(flag.sum()), "derived",
        "is_subscription set from selling_plan_id presence on the line item",
    )
    return df


SPEC = DatasetSpec(
    name="shopify_order_items.csv",
    role="order_items",
    source_files=["shopify_order_items.csv"],
    key="line_item_id",
    required=["order_id", "line_item_id", "product_id"],
    lower_enum_cols=["fulfillment_status"],
    fks=[("order_id", "orders", "id"), ("product_id", "products", "product_id")],
    post_hooks=[add_is_subscription],
)
