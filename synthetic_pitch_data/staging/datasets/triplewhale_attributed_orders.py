"""Stage cleaner for Triple Whale attributed orders. Reusable across Triple Whale clients.

Deduplicates to one attribution row per order (Triple Whale can emit replayed rows
sharing an order_id with distinct triple_ids).
"""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="triple_whale_attributed_orders.csv",
    role="attribution_orders",
    source_files=[
        "triple_whale_attributed_orders.csv",
        "triplewhale_customer_journey_attribution_orders.csv",
    ],
    key="order_id",
    required=["order_id"],
    timestamp_cols=["created_at", "click_ts"],
    email_cols=["customer_email"],
    upper_cols=["currency"],
    lower_enum_cols=["channel"],
    fks=[("order_id", "orders", "id"), ("customer_id", "customers", "id")],
)
