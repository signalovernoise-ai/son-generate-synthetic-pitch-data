# Stage Cleaning & Standardization

How raw source extracts become cleaned, standardized **stage** tables. The runnable
implementation is the `synthetic_pitch_data/staging` package; this doc is the
methodology and the contract for extending it.

## Hard rule: discover issues from the data, never from the generator

Cleaning must find issues by **profiling the data**, exactly as a real data team
would for a brand-new client. Do **not** read the generators
(`synthetic_pitch_data/company/*`, `config.py`, injected-issue lists) to learn what
quirks exist. The staging package is deliberately isolated and must never import
generator code. Knowing a column's *name and role* is fine (that is real schema
knowledge); knowing what was *injected* is not.

## Canonical stage targets

- **Commerce backend spine — standardize to the Shopify shape.** `customers`,
  `orders`, `order_items`, `products` are cleaned into Shopify-named tables. A
  non-Shopify backend (e.g. custom Postgres) is first conformed to that shape by an
  **adapter** (`staging/adapters/<backend>.py`), after which the standard Shopify
  cleaners apply unchanged. Derived canonical fields: `net_sale_price` (refund-netted)
  on orders, `is_subscription` (selling-plan presence) on order items.
- **Non-commerce systems — clean within their own standard source schema.** GA4,
  Bloomreach, Klaviyo, Zendesk, OrderGroove, Triple Whale are not orders; each is cleaned
  and standardized in its own documented shape (see `standard-source-schemas/`). They are
  not forced into the Shopify shape.
- **Ad platforms (Google Ads, Meta) — clean within their own shape, then conform to a
  shared `ad_performance` metric vocabulary.** Each platform stays faithful to its API
  (Google's dotted GAQL fields + `cost_micros`; Meta's `actions`/`action_values` arrays),
  and its cleaner derives canonical columns (`date`, `platform`, `account_id`,
  `campaign_id`, `impressions`, `clicks`, `spend`, `conversions`, `conversion_value`) so the
  cleaned tables can be unioned into one cross-platform performance view. They are aggregate
  daily facts and do not join to the commerce spine.

Metric conventions (net-of-discount, VAT-inclusive, etc.) follow `metric-definitions.md`.

## Two layers

1. **Runtime (deterministic, reusable).** `staging/run_staging.py` runs each dataset
   through a fixed **detector battery** in dependency order, writes cleaned tables, and
   generates `CLEANING_NOTES.md` from what the battery actually found. No LLM, no
   per-client logic. Per-dataset cleaners live in `staging/datasets/<name>.py` and are
   reused across every client on that system — never per client.
2. **Onboarding a new system or new quirk (agentic).** When a new client brings a
   system or a quirk the battery does not yet handle: profile the data (diff against the
   standard schema, inspect distributions, eyeball anomalies), then either reuse an
   existing detector or **add a new detector to the shared battery** and a thin dataset
   spec. This is how the cleaner is refined over time.

## Detector battery (current)

Each detector measures and reports a count; the notes are rendered from these findings.

| Detector | What it does | Action |
|---|---|---|
| `missing_required_fields` | required key/timestamp absent | remove row |
| `duplicate_primary_key` | repeated key | remove (keep first) |
| `duplicate_display_id` | repeated human display id, key still unique | flag, **retain** |
| `test_internal_rows` | test/QA/dev/staging/@example patterns | remove row |
| `email_casing_whitespace` | lower/trim emails | normalize |
| `country_normalization` | map country aliases → canonical code | normalize |
| `enum_casing_drift` | collapse a value that appears under mixed casings | normalize (drift only) |
| `implausible_amount` | order value outside sane bounds | remove row |
| `timestamp_reversal` | e.g. `processed_at < created_at` | remove row |
| `near_duplicate_rows` | same group + amount within N seconds (retries) | remove row |
| `orphan_foreign_key` | FK value not in cleaned parent | remove row |
| `non_final_status` | status outside the final/keep set (cancelled, pending…) | remove row |
| `refund_netting` | derive `net_sale_price = total − refunded` | derive |
| `subscription_flag` | derive `is_subscription` from selling-plan | derive |

`enum_casing_drift` only fires on **genuine** drift (one normalized value with more than
one raw spelling); consistently-cased columns are left untouched so the notes don't
report a blanket re-casing as a defect. Cross-system coverage gaps (e.g. orders missing
from an attribution source) are reported **window-aware** and **retained** — they are a
real-world property to surface, not rows to delete.

## How to extend

- **New client, known systems:** nothing to write. Run `run_staging --company <slug>`.
- **New non-Shopify commerce backend:** add `staging/adapters/<backend>.py` exposing
  `detect(src)` and `adapt(src) -> {shopify_filename: DataFrame}`; the standard Shopify
  cleaners then run.
- **New source system (non-commerce):** add `staging/datasets/<system>.py` with a
  `DatasetSpec` (key, timestamps, enums, FKs, etc.) and register it in
  `staging/schema_registry.py` in dependency order.
- **New quirk:** add a detector to `staging/cleaning_common.py`, wire it into
  `engine.run_dataset`, and (if it has a measurable signature) consider also adding a
  `validate_raw` check so generation is held to it.

## Output

Per company under `data/stage/<slug>/`: one cleaned table per dataset (canonical names)
plus `CLEANING_NOTES.md` with a per-dataset section and a cross-system coverage section.
Analytics (e.g. `monthly_cohort_retention`) reads the cleaned commerce tables directly.
