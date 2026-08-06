"""Stage cleaner for Gorgias tickets. Reusable across all Gorgias clients.

Gorgias is ecommerce-native, so tickets can carry the linked Shopify customer and
order — but that linkage is agent-applied, not guaranteed. Blank ids are retained
(the orphan check skips them); populated ids must resolve to a staged parent.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec


def measure_commerce_linkage(df: pd.DataFrame, report) -> pd.DataFrame:
    """Support volume that cannot be joined to commerce is a property to surface, not
    rows to delete."""
    for col, label in [("shopify_order_id", "order"), ("shopify_customer_id", "customer")]:
        if col not in df.columns:
            continue
        missing = int(df[col].astype("string").fillna("").str.strip().eq("").sum())
        if missing:
            report.record(
                "unlinked_support_ticket", missing, "flagged",
                f"{missing:,} tickets ({missing / len(df):.1%}) have no {label} link (retained)",
            )
    return df


SPEC = DatasetSpec(
    name="gorgias_tickets.csv",
    role="support_tickets",
    source_files=["gorgias_tickets.csv"],
    key="id",
    required=["id", "created_datetime"],
    timestamp_cols=[
        "created_datetime", "updated_datetime", "opened_datetime",
        "closed_datetime", "trashed_datetime",
    ],
    reversal_pairs=[
        ("created_datetime", "updated_datetime"),
        ("opened_datetime", "closed_datetime"),
    ],
    primary_timestamp="created_datetime",
    email_cols=["from_email"],
    lower_enum_cols=["status", "priority", "channel", "via", "tags", "language"],
    test_pattern_cols=["from_email", "subject"],
    fks=[
        ("shopify_order_id", "orders", "id"),
        ("shopify_customer_id", "customers", "id"),
    ],
    provides_keys=["id"],
    pre_hooks=[measure_commerce_linkage],
    static_notes=[
        "channel (where the conversation happened) and via (how it entered) are distinct and "
        "routinely disagree; both are kept.",
        "satisfaction_score is 1-5 and is populated on only a minority of closed tickets. Do not "
        "map it onto the Zendesk good/bad enum in this layer.",
    ],
)
