"""Stage cleaner for the Meta ad-creative dimension. Reusable across Meta clients.

One row per ad; joins to meta_ads_insights on ad_id for creative-level reporting.
"""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="meta_ad_creatives.csv",
    role="ad_creative",
    source_files=["meta_ad_creatives.csv"],
    key="ad_id",
    required=["ad_id", "creative_id"],
    lower_enum_cols=["object_type", "call_to_action_type"],
)
