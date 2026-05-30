"""Stage cleaner for Bloomreach campaign events. Reusable across Bloomreach clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="bloomreach_campaign_events.csv",
    role="crm_events",
    source_files=["bloomreach_campaign_events.csv"],
    required=["timestamp"],
    timestamp_cols=["timestamp", "sent_timestamp"],
    email_cols=["recipient"],
    country_cols=["country"],
    lower_enum_cols=["status", "action_type", "consent_category"],
    test_pattern_cols=["recipient"],
)
