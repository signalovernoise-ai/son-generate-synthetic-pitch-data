# Meta Ads

Use the Meta Marketing **Insights API** as the standard source for Facebook/Instagram paid
**delivery & spend performance**, pulled via API (not a data warehouse).

Like Google Ads (`google-ads.md`) this is **platform-reported ad performance** (logical role
`ad_performance`): aggregate daily facts keyed by ad object, with no order or customer foreign
key. It is distinct from Triple Whale (order-level attribution) and GA4 (web analytics).

Important:

- The **Insights API** is the reporting "edge" of the Marketing API. Query it with a `level`
  parameter (`account` / `campaign` / `adset` / `ad`) and `time_increment=1` for a daily series.
- We pull at **`level=ad`** — the finest grain — which **rolls up to adset and campaign** via
  the IDs carried on every row (`campaign_id`/`adset_id`/`ad_id` + names). One ad-level extract
  therefore delivers the campaign / adset / creative levels the brief asks for, without three
  separate pulls.
- **Spend is in account currency** (not micros, unlike Google).
- `actions` and `action_values` are **arrays of `{action_type, value}`**, JSON-encoded in the
  CSV. Purchases come from `action_type` in `purchase` / `omni_purchase` /
  `offsite_conversion.fb_pixel_purchase`. The stage layer parses these into canonical
  `conversions` / `conversion_value`. These are Meta's attributed conversions (pixel/CAPI), not
  the Shopify order count.
- Creative metadata is **not** on the Insights edge — it lives on the ad/creative object. Pull
  it separately (`meta_ad_creatives.csv`) and join on `ad_id` to get creative-level reporting.

## Ad-level insights (standard grain)

Daily ad-level performance. One row per (`date_start`, `ad_id`); with `time_increment=1`,
`date_start` = `date_stop`.

`meta_ads_insights.csv`

- `date_start`
- `date_stop`
- `account_id`
- `account_name`
- `account_currency`
- `campaign_id`
- `campaign_name`
- `objective`
- `adset_id`
- `adset_name`
- `ad_id`
- `ad_name`
- `impressions`
- `reach`
- `frequency`
- `clicks`
- `inline_link_clicks`
- `spend`
- `cpc`
- `cpm`
- `ctr`
- `actions`
- `action_values`
- `purchase_roas`

Notes:

- `objective` is the campaign objective enum (e.g. `OUTCOME_SALES`, `OUTCOME_TRAFFIC`,
  `OUTCOME_AWARENESS`).
- `reach` and `frequency` are people-based (reach = unique people, frequency = impressions per
  person); they do not sum across rows the way impressions do.
- `cpc`, `cpm`, `ctr`, `purchase_roas` are returned by the API as derived figures — carry as
  reported, do not recompute.
- `actions` / `action_values` / `purchase_roas` are JSON-encoded arrays. Keep the raw arrays;
  derive canonical conversion columns downstream.

## Creative dimension

Creative attributes for ad-level reporting, pulled from the ad/creative object and joined on
`ad_id`. One row per ad.

`meta_ad_creatives.csv`

- `ad_id`
- `creative_id`
- `creative_name`
- `object_type`
- `call_to_action_type`
- `title`
- `body`
- `thumbnail_url`
- `instagram_permalink_url`
- `effective_object_story_id`

Notes:

- `object_type` indicates the creative format (e.g. `VIDEO`, `SHARE`, `PHOTO`).
- Multiple ads may reference the same underlying creative; key this table by `ad_id` so it
  joins cleanly to the insights extract.

## Standardised cross-platform view

The stage cleaner conforms the insights extract to the shared `ad_performance` metric
vocabulary so it can be unioned with Google Ads: canonical keys `date`, `platform` (`meta`),
`account_id`, `campaign_id`, `campaign_name`, `adset_id`, `ad_id`, `level` (`ad`), `currency`;
canonical metrics `impressions`, `clicks`, `spend`, `conversions` / `conversion_value` (parsed
from `actions` / `action_values`). Native fields and the raw action arrays are retained
alongside the canonical ones.
