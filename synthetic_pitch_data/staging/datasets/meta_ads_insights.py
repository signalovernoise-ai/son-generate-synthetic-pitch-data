"""Stage cleaner for Meta (Facebook/Instagram) ad-level insights. Reusable across Meta clients.

Conforms the Insights API ad-level extract to the shared `ad_performance` metric vocabulary,
parsing the `actions` / `action_values` arrays into canonical conversions so it can be unioned
with Google Ads. Native fields and the raw action arrays are retained alongside.
"""

from __future__ import annotations

import json

import pandas as pd

from ..cleaning_common import DatasetSpec, StageReport

# Meta action_types that represent a purchase conversion across pixel / CAPI / on-Meta.
PURCHASE_ACTION_TYPES = {
    "purchase",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
}


def _sum_purchase_actions(blob: object) -> float:
    """Sum the `value` of purchase action_types in a JSON-encoded actions array."""
    if not isinstance(blob, str) or not blob.strip():
        return 0.0
    try:
        arr = json.loads(blob)
    except (ValueError, TypeError):
        return 0.0
    if not isinstance(arr, list):
        return 0.0
    total = 0.0
    for a in arr:
        if isinstance(a, dict) and a.get("action_type") in PURCHASE_ACTION_TYPES:
            try:
                total += float(a.get("value", 0) or 0)
            except (ValueError, TypeError):
                continue
    return total


def _standardize(df: pd.DataFrame, report: StageReport) -> pd.DataFrame:
    df = df.copy()
    if "actions" in df.columns:
        df["conversions"] = df["actions"].map(_sum_purchase_actions)
    if "action_values" in df.columns:
        df["conversion_value"] = df["action_values"].map(_sum_purchase_actions).round(2)
    if "actions" in df.columns or "action_values" in df.columns:
        report.note("derived conversions/conversion_value from purchase action_types")
    df["platform"] = "meta"
    df["level"] = "ad"
    return df


SPEC = DatasetSpec(
    name="meta_ads_insights.csv",
    role="ad_performance",
    source_files=["meta_ads_insights.csv"],
    required=["date", "ad_id"],  # checked post field_map rename
    field_map={
        "date_start": "date",
        "account_currency": "currency",
    },
    lower_enum_cols=["objective"],
    post_hooks=[_standardize],
)
