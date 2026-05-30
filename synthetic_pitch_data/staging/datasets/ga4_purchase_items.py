"""Stage cleaner for GA4 reporting purchase items. Reusable across GA4 clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="ga4_reporting_purchase_items.csv",
    role="ga4_items",
    source_files=["ga4_reporting_purchase_items.csv", "ga4_reporting_order_items.csv"],
    required=["transactionId", "itemId"],
    fks=[("transactionId", "orders", "id")],
)
