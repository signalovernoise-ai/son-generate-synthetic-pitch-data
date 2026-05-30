"""Stage cleaner for OrderGroove subscriptions. Reusable across OrderGroove clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="ordergroove_subscriptions.csv",
    role="subscriptions",
    source_files=["ordergroove_subscriptions.csv"],
    key="publicId",
    required=["publicId"],
    timestamp_cols=["startDate", "created", "updated", "cancelled"],
    upper_cols=["currencyCode"],
    lower_enum_cols=["subscriptionType", "everyPeriod", "cancelReason"],
    provides_keys=["publicId"],
)
