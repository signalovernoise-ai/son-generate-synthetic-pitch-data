"""Stage cleaner for TikTok ad-level insights. Reusable across all TikTok clients.

Conforms the Business API reporting extract to the shared `ad_performance` metric vocabulary
so it can be unioned with Google Ads and Meta. Native fields, including the full video
completion ladder, are retained alongside the canonical columns.

Two TikTok-specific traps are handled here:

- **`conversion` is not the purchase.** `conversion` is whatever the ad group optimises for;
  `complete_payment` is the purchase event. Mapping the wrong one makes TikTok look several
  times more efficient than Meta and Google in a side-by-side. Canonical `conversions` is
  taken from `complete_payment`.
- **Metrics arrive as strings.** The reporting API returns numerics quoted, so every metric
  is coerced explicitly rather than relying on inferred dtypes.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec, StageReport

NUMERIC_COLS = [
    "impressions", "reach", "frequency", "clicks", "spend", "cpc", "cpm", "ctr",
    "conversion", "cost_per_conversion", "conversion_rate", "complete_payment",
    "complete_payment_roas", "total_purchase_value", "video_play_actions",
    "video_watched_2s", "video_watched_6s", "video_views_p25", "video_views_p50",
    "video_views_p75", "video_views_p100", "average_video_play",
]

# Completion ladder, widest funnel stage first. Each stage must be <= the one before it.
VIDEO_LADDER = [
    "video_play_actions", "video_views_p25", "video_views_p50",
    "video_views_p75", "video_views_p100",
]


def _coerce_numerics(df: pd.DataFrame, report: StageReport) -> pd.DataFrame:
    df = df.copy()
    coerced = 0
    for col in NUMERIC_COLS:
        if col in df.columns and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            coerced += 1
    if coerced:
        report.record(
            "type_drift", coerced, "normalized",
            "TikTok's reporting API returns numeric metrics as quoted strings; coerced to numeric",
        )
    return df


def _check_video_ladder(df: pd.DataFrame, report: StageReport) -> pd.DataFrame:
    present = [c for c in VIDEO_LADDER if c in df.columns]
    if len(present) < 2:
        return df
    bad = pd.Series(False, index=df.index)
    for wider, narrower in zip(present, present[1:]):
        bad |= pd.to_numeric(df[narrower], errors="coerce") > pd.to_numeric(df[wider], errors="coerce")
    n = int(bad.sum())
    report.record(
        "video_ladder_monotonic", n, "flagged" if n else "none",
        f"{n:,} rows where a deeper video-completion stage exceeds a shallower one"
        if n else "completion ladder is monotonic on every row",
    )
    return df


def _standardize(df: pd.DataFrame, report: StageReport) -> pd.DataFrame:
    df = df.copy()
    if "complete_payment" in df.columns:
        df["conversions"] = pd.to_numeric(df["complete_payment"], errors="coerce")
        report.note(
            "canonical conversions mapped from complete_payment (the purchase event), NOT from "
            "conversion (the ad group's optimisation event) — mapping the latter overstates "
            "TikTok efficiency against Meta and Google"
        )
    if "total_purchase_value" in df.columns:
        df["conversion_value"] = pd.to_numeric(df["total_purchase_value"], errors="coerce").round(2)
    if "advertiser_id" in df.columns:
        df["account_id"] = df["advertiser_id"]
    if "adgroup_id" in df.columns:
        df["adset_id"] = df["adgroup_id"]   # TikTok's adgroup is Meta's adset
    df["platform"] = "tiktok"
    df["level"] = "ad"
    return df


SPEC = DatasetSpec(
    name="tiktok_ads_insights.csv",
    role="ad_performance",
    source_files=["tiktok_ads_insights.csv"],
    required=["date", "ad_id"],  # checked post field_map rename
    field_map={"stat_time_day": "date"},
    upper_cols=["currency"],
    lower_enum_cols=["objective_type", "placement_type", "identity_type"],
    pre_hooks=[_coerce_numerics, _check_video_ladder],
    post_hooks=[_standardize],
    static_notes=[
        "identity_type separates brand-owned creative (customized_user) from Spark Ads running "
        "through a creator's own handle (auth_code / tt_user). It is the only place the creator "
        "relationship appears in performance data.",
        "reach and frequency are people-based and do not sum across rows the way impressions do.",
    ],
)
