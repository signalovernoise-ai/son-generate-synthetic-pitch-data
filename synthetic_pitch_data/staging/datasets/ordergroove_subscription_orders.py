"""Stage cleaner for OrderGroove subscription orders. Reusable across OrderGroove clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="ordergroove_subscription_orders.csv",
    role="subscription_orders",
    source_files=["ordergroove_subscription_orders.csv"],
    key="publicId",
    required=["publicId"],
    timestamp_cols=["created", "updated", "cancelled", "place"],
    upper_cols=["currencyCode"],
    lower_enum_cols=["status"],
)
