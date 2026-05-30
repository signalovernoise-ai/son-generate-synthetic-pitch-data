"""Stage cleaner for OrderGroove events. Reusable across OrderGroove clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="ordergroove_events.csv",
    role="subscription_events",
    source_files=["ordergroove_events.csv"],
    key="id",
    required=["id"],
    timestamp_cols=["created"],
    lower_enum_cols=["type", "object_type"],
)
