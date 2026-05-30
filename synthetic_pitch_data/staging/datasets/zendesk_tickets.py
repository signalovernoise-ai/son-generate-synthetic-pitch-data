"""Stage cleaner for Zendesk tickets. Reusable across Zendesk clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="zendesk_tickets.csv",
    role="support_tickets",
    source_files=["zendesk_tickets.csv"],
    key="id",
    required=["id", "created_at"],
    timestamp_cols=["created_at", "updated_at"],
    reversal_pairs=[("created_at", "updated_at")],
    lower_enum_cols=["status", "priority", "type", "via_channel"],
)
