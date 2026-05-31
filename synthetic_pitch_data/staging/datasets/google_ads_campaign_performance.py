"""Stage cleaner for Google Ads campaign performance. Reusable across Google Ads clients.

Conforms the GAQL campaign report to the shared `ad_performance` metric vocabulary
(date/platform/account/campaign + impressions/clicks/spend/conversions/conversion_value)
so it can be unioned with Meta. Native dotted GAQL fields are retained alongside.
"""

from __future__ import annotations

import pandas as pd

from ..cleaning_common import DatasetSpec, StageReport


def _standardize(df: pd.DataFrame, report: StageReport) -> pd.DataFrame:
    df = df.copy()
    # Cost is in micros (millionths of the account currency).
    if "metrics.cost_micros" in df.columns:
        df["spend"] = (pd.to_numeric(df["metrics.cost_micros"], errors="coerce") / 1_000_000).round(2)
        report.note("derived spend = metrics.cost_micros / 1,000,000")
    df["platform"] = "google_ads"
    df["level"] = "campaign"
    return df


# field_map renames the 1:1 GAQL fields to the canonical ad_performance vocabulary.
# cost_micros is left raw and converted to `spend` in the post-hook.
SPEC = DatasetSpec(
    name="google_ads_campaign_performance.csv",
    role="ad_performance",
    source_files=["google_ads_campaign_performance.csv"],
    required=["date", "campaign_id"],  # checked post field_map rename
    field_map={
        "segments.date": "date",
        "customer.id": "account_id",
        "customer.descriptive_name": "account_name",
        "customer.currency_code": "currency",
        "campaign.id": "campaign_id",
        "campaign.name": "campaign_name",
        "campaign.status": "campaign_status",
        "campaign.advertising_channel_type": "channel_type",
        "metrics.impressions": "impressions",
        "metrics.clicks": "clicks",
        "metrics.conversions": "conversions",
        "metrics.conversions_value": "conversion_value",
    },
    lower_enum_cols=["channel_type", "campaign_status"],
    post_hooks=[_standardize],
)
