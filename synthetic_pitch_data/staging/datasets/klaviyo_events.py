"""Stage cleaner for Klaviyo email/SMS events. Reusable across Klaviyo clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="klaviyo_events.csv",
    role="crm_events",
    source_files=["klaviyo_events.csv"],
    key="event_id",
    required=["event_id", "timestamp"],
    timestamp_cols=["timestamp"],
    email_cols=["email"],
    lower_enum_cols=["channel", "bounce_type"],
    test_pattern_cols=["email"],
)
