# TikTok Ads

Use the TikTok **Business API reporting endpoint** (`/report/integrated/get/`) as the standard
source for TikTok paid **delivery & spend performance**, pulled via API (not a data warehouse).

Like Google Ads (`google-ads.md`) and Meta Ads (`meta-ads.md`) this is **platform-reported ad
performance** (logical role `ad_performance`): aggregate daily facts keyed by ad object, with no
order or customer foreign key. It is distinct from Triple Whale (order-level attribution) and GA4
(web analytics).

Detection: the TikTok Commercial Content Library
(`library.tiktok.com/ads`, searchable by advertiser and region) is the strongest public evidence
and works even when the pixel is invisible — on a Shopify store the TikTok pixel usually sits in
the server-side web-pixels sandbox, so `analytics.tiktok.com` will **not** appear in the rendered
page source. Do not read a missing pixel as absence of the channel; check the ad library.

Important:

- Query with `report_type=BASIC`, `data_level=AUCTION_AD`, `dimensions=["ad_id","stat_time_day"]`
  for a daily ad-level series. We pull at **ad level** — the finest grain — which **rolls up to
  adgroup and campaign** via the ids carried on every row.
- TikTok's hierarchy is **campaign → adgroup → ad**. Note it is `adgroup`, not Meta's `adset`;
  keep the native naming in the raw extract and let the stage layer conform it.
- **Spend is in account currency**, like Meta and unlike Google's micros.
- Metrics are returned as **strings** in the API response, including numeric ones. Type drift
  between extracts is a genuine TikTok quirk worth preserving where a data issue calls for it.
- Conversions are TikTok's own pixel/Events-API-attributed figures, not the Shopify order count.
  `conversion` is the optimisation event; `complete_payment` is the purchase event and is the one
  that should be compared to commerce. They are different columns and are routinely confused.
- Video metrics are first-class here in a way they are not on Google or Meta. TikTok is a
  video-native placement and `video_views_p25/p50/p75/p100` plus `average_video_play` are the
  metrics buyers actually optimise against. Carry them.
- `identity_type` distinguishes brand-owned posts from **Spark Ads** running through a creator's
  own handle (`TT_USER` / `AUTH_CODE`). For brands that run creator whitelisting this is the only
  place the creator relationship is visible in the performance data.

## Ad-level insights (standard grain)

Daily ad-level performance. One row per (`stat_time_day`, `ad_id`).

`tiktok_ads_insights.csv`

- `stat_time_day`
- `advertiser_id`
- `advertiser_name`
- `currency`
- `campaign_id`
- `campaign_name`
- `objective_type`
- `adgroup_id`
- `adgroup_name`
- `placement_type`
- `ad_id`
- `ad_name`
- `identity_type`
- `impressions`
- `reach`
- `frequency`
- `clicks`
- `spend`
- `cpc`
- `cpm`
- `ctr`
- `conversion`
- `cost_per_conversion`
- `conversion_rate`
- `complete_payment`
- `complete_payment_roas`
- `total_purchase_value`
- `video_play_actions`
- `video_watched_2s`
- `video_watched_6s`
- `video_views_p25`
- `video_views_p50`
- `video_views_p75`
- `video_views_p100`
- `average_video_play`

Notes:

- `objective_type` is the campaign objective enum (`CONVERSIONS`, `PRODUCT_SALES`, `TRAFFIC`,
  `REACH`, `VIDEO_VIEWS`, `LEAD_GENERATION`).
- `placement_type` is `PLACEMENT_TYPE_AUTOMATIC` or `PLACEMENT_TYPE_NORMAL`.
- `identity_type` is `CUSTOMIZED_USER` (brand-owned creative), `TT_USER` (posting as a TikTok
  account) or `AUTH_CODE` (Spark Ad authorised from a creator's post).
- `reach` and `frequency` are people-based; they do not sum across rows the way impressions do.
- `cpc`, `cpm`, `ctr`, `cost_per_conversion`, `conversion_rate` and `complete_payment_roas` are
  returned as derived figures — carry as reported, do not recompute.
- `video_play_actions` counts plays; `video_watched_2s` / `_6s` are the thresholds TikTok bills and
  reports against. `video_views_p100` is completions, so `p100 <= p75 <= p50 <= p25 <=
  video_play_actions` must hold on every row.
- There is no separate creative dimension table. TikTok creative metadata (video id, thumbnail,
  caption) sits on the ad object and is only worth pulling when the brief needs creative-level
  analysis; when it is, add `tiktok_ad_creatives.csv` keyed on `ad_id` following the Meta pattern.

## Standardised cross-platform view

The stage cleaner conforms this extract to the shared `ad_performance` metric vocabulary so it can
be unioned with Google Ads and Meta Ads: canonical keys `date`, `platform` (`tiktok`),
`account_id` (from `advertiser_id`), `campaign_id`, `campaign_name`, `adset_id` (from
`adgroup_id`), `ad_id`, `level` (`ad`), `currency`; canonical metrics `impressions`, `clicks`,
`spend`, `conversions` (from `complete_payment`) and `conversion_value` (from
`total_purchase_value`). Native fields including the full video-completion ladder are retained
alongside the canonical ones.

Mapping the conversion columns is the one place to be careful: use `complete_payment`, not
`conversion`, or TikTok will look several times more efficient than Meta and Google in a
side-by-side.
