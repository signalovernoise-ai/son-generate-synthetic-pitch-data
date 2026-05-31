# Google Ads

Use the Google Ads API (GAQL reporting) as the standard source for Google paid-search and
shopping **delivery & spend performance** — what the platform self-reports, pulled via API,
not from a data warehouse.

This is **platform-reported ad performance** (spend, impressions, clicks, platform-attributed
conversions) and is distinct from:

- **Triple Whale** (`triple-whale.md`) — cross-channel *attribution* of individual orders.
- **GA4** (`ga4-reporting-api.md`) — web-analytics sessions and ecommerce.

Google Ads and Meta (`meta-ads.md`) together form the standard **paid-media performance**
layer, logical role `ad_performance`. They are aggregate daily facts keyed by ad object and
do **not** join to the commerce spine — there is no order or customer foreign key.

Important:

- Reporting is via **GAQL** against the `campaign` resource with `segments.date` for a daily
  time series. Field names are the documented dotted resource.field names (e.g.
  `metrics.cost_micros`); keep them verbatim as column headers — they are the API schema.
- **Cost is in micros.** `metrics.cost_micros` is millionths of the account currency; divide
  by 1,000,000 for spend. The stage layer derives a canonical `spend`.
- Rate metrics (`metrics.ctr`, `metrics.average_cpc`, `metrics.average_cpm`) are returned by
  the API as derived figures — carry them as reported, do not recompute and overwrite.
- `metrics.conversions` / `metrics.conversions_value` reflect the account's conversion-action
  configuration and attribution settings; they are Google's attributed conversions, not the
  Shopify order count. `all_conversions*` include actions not set to "include in conversions".

## Campaign performance (standard grain)

Daily campaign-level performance. One row per (`segments.date`, `campaign.id`).

`google_ads_campaign_performance.csv`

- `segments.date`
- `customer.id`
- `customer.descriptive_name`
- `customer.currency_code`
- `campaign.id`
- `campaign.name`
- `campaign.status`
- `campaign.advertising_channel_type`
- `campaign.bidding_strategy_type`
- `metrics.impressions`
- `metrics.clicks`
- `metrics.cost_micros`
- `metrics.conversions`
- `metrics.conversions_value`
- `metrics.all_conversions`
- `metrics.all_conversions_value`
- `metrics.ctr`
- `metrics.average_cpc`
- `metrics.average_cpm`
- `metrics.search_impression_share`

Notes:

- `campaign.advertising_channel_type` is an upper-case enum: `SEARCH`, `SHOPPING`, `DISPLAY`,
  `PERFORMANCE_MAX`, `VIDEO`, `DEMAND_GEN`. Use it to segment campaign types.
- `customer.id` is the Google Ads account; `customer.currency_code` is the spend currency.
- The natural key is composite (`segments.date` + `campaign.id`); there is no native row id.

## Finer grain (optional, addable per client)

When a client needs ad-group or ad/creative-level Google detail, add a finer extract per the
same pattern rather than over-pulling by default:

- ad group: `ad_group` resource → `google_ads_ad_group_performance.csv` (adds `ad_group.id`,
  `ad_group.name`).
- ad / creative: `ad_group_ad` resource → `google_ads_ad_performance.csv` (adds
  `ad_group_ad.ad.id`, `ad_group_ad.ad.name`, `ad_group_ad.ad.type`).

Campaign-level is the default standard because it is universally available and is the grain
most clients report Google performance at. Google's "creative" concept (responsive search
ads, asset-level reporting) is messier than Meta's one-ad-one-creative model, so it is opt-in.

## Standardised cross-platform view

The stage cleaner conforms this extract to the shared `ad_performance` metric vocabulary so it
can be unioned with Meta (see `meta-ads.md`): canonical keys `date`, `platform` (`google_ads`),
`account_id`, `campaign_id`, `campaign_name`, `level` (`campaign`), `currency`; canonical
metrics `impressions`, `clicks`, `spend` (derived from `metrics.cost_micros`), `conversions`,
`conversion_value`. Native fields are retained alongside the canonical ones.
