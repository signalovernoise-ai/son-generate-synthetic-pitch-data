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
    # Line-economics profiling: separates non-merchandise lines (shipping protection,
    # warranties), gift-with-purchase zero-value lines, and one-variant-many-prices
    # dispersion. All flagged and retained so order totals still reconcile.
    line_product_col="product_id",
    line_variant_col="variant_id",
    line_price_col="discounted_price",
    line_list_price_col="price",
    line_discount_col="total_discount",
    requires_shipping_col="requires_shipping",
    post_hooks=[add_is_subscription],
    static_notes=[
        "is_merchandise excludes non-merchandise lines; use it before any per-SKU revenue, "
        "attach-rate or units-sold analysis, or those figures include insurance/warranty upsells.",
        "is_zero_value_line marks gift-with-purchase and lead-magnet lines. They are real "
        "fulfilled lines, so they count toward units but not revenue.",
    ],
)
