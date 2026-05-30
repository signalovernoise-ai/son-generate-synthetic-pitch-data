"""Stage cleaner for Triple Whale customer-journey events. Reusable across Triple Whale clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="triple_whale_customer_journey_events.csv",
    role="attribution_events",
    source_files=["triple_whale_customer_journey_events.csv"],
    required=["order_id", "event_time"],
    timestamp_cols=["event_time", "lead_click_ts"],
    email_cols=["email"],
    lower_enum_cols=["type", "event_name"],
    fks=[("order_id", "orders", "id")],
)
