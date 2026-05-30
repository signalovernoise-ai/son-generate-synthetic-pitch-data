"""Stage cleaner for GA4 reporting purchase events. Reusable across GA4 clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="ga4_reporting_purchase_events.csv",
    role="ga4_events",
    source_files=["ga4_reporting_purchase_events.csv", "ga4_reporting_orders.csv"],
    key="transactionId",
    required=["transactionId", "date"],
    country_cols=["country"],
    fks=[("transactionId", "orders", "id")],
    static_notes=[
        "Unassigned/(not set) channel rows are retained: they reflect real attribution gaps, "
        "not dirty rows. GA4 compact dates (YYYYMMDD) are left as-is.",
    ],
)
