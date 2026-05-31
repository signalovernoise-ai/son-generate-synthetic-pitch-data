# Generator Authoring Contract

Read this **before writing a new company `generate_raw.py`**. It is the authoring contract
for per-company raw generators. The point is to stop new generators being reverse-engineered
from the last company's code — that is how drift creeps in.

> The output is already contracted by `validate_raw` (executable), the
> `standard-source-schemas/` docs (column shapes), and `RAW_SCHEMA` (keys/FKs/roles). This
> doc adds the missing piece: how the *generator itself* should be structured and what
> conventions it must follow.

## Where generators live

```
synthetic_pitch_data/company/<slug>/
  __init__.py
  config.py          # constants + product specs + monthly target series
  generate_raw.py    # builders + main(); run: python3 -m ...company.<slug>.generate_raw
```

Run with `python3 -m synthetic_pitch_data.company.<slug>.generate_raw`. Outputs go to the
**external** workspace via `raw_common.write_source_csv(df, "<slug>", "<canonical>.csv")` —
never write generated CSVs into the repo.

> Note (cleanup deferred): two generator patterns currently coexist — the older
> `shopify_1/2`, `postgresql_1` split (`orders.py` + `users.py`, wired into `run_all.py`) and
> the newer monolithic `generate_raw.py` (`yumove`, `luminary`). New companies use the
> **monolithic `generate_raw.py`** pattern. Unifying the old pattern and extracting the
> shared helpers below into a `company/_generator_common.py` is a planned cleanup, deferred
> until those clients leave the pipeline. Until then, copy the shared helpers from an existing
> monolithic generator **with identical signatures** so the eventual extraction is mechanical.

## config.py contract

- `BUSINESS = "<slug>"`, `SEED = <int>` (one base seed), `ROW_SCALE` (1.0 unless volume-gated).
- Window constants: `SOURCE_WINDOW_START/END`, plus any source-specific starts (e.g.
  `KLAVIYO_START`, `GOOGLE_ADS_START`). These must match the setup yaml
  `source_specific_window_bounds`.
- A frozen `ProductSpec` dataclass + a `PRODUCTS` list grounded in the live catalog (current
  prices/names) plus a few adjacent legacy/delisted SKUs.
- Monthly target series keyed `YYYY-MM` over the full window: at minimum
  `MONTHLY_ORDER_TARGETS` and `MONTHLY_AOV`. These are the source of truth the
  `metric_trajectory` check validates against — keep them consistent with the yaml
  `revenue_by_period / orders_by_period / aov_by_period` (revenue == orders × AOV per month).

## generate_raw.py contract

- **Determinism:** seed every builder from the base seed with a distinct offset
  (`np.random.default_rng(SEED + n)`), so a rerun is byte-identical and builders are
  independent.
- **The spine, in order:** `build_products()` → `build_core_sources()` (orders + customers +
  order_items) → then dependent system builders. Downstream builders consume the spine
  outputs as ground truth; they never invent their own customers/orders.
- **Canonical output names:** every file written must be a canonical filename present in
  `RAW_SCHEMA` / the matching `standard-source-schemas/` doc, with that doc's columns.
- `main()` calls the builders in dependency order and writes via a `write_outputs` map.

### Shared helpers (reuse, identical signatures)

These are currently duplicated across monolithic generators and are the planned extraction
target. Reuse them verbatim: `to_iso`, `month_start/month_end`, `random_timestamp_in_month`,
`random_timestamp_after` (repeat orders must not predate `customer.created_at`),
`weighted_choice`, `make_email`, `drift_email`, the Shopify `customers`/`orders`/`order_items`
row shapes, and `write_outputs`.

## Metric calibration

- AOV and revenue are **net of discount, shipping-excluded** (and VAT-inclusive where VAT
  applies) — see `metric-definitions.md`. Calibrate against the net price the customer pays,
  never gross `compare_at_price`.
- **Pin order counts** to `MONTHLY_ORDER_TARGETS` so orders (and revenue) match exactly;
  then calibrate AOV so revenue follows.
- **AOV technique by catalog type:**
  - *No list-price discount* (sell == compare_at; discounts applied explicitly at the line):
    size each order so `E[total_price] == month AOV target` via `P(2 units) = target/unit_net − 1`.
    This is exact per-order and avoids the gross/compare_at miscalibration.
  - *List-price discounts present:* build the basket toward the **net** target, not the gross
    list total.
- Monthly volume targets are **promo-inclusive**; model promo effects on AOV/mix, not as an
  extra volume lift.

## Cross-system consistency rules (do not skip)

- **Keys/FKs reconcile** across systems (the spine's ids are the only source of truth).
- **Timestamps:** downstream events are plausible vs the order; repeat/renewal orders are
  `≥ customer.created_at` (no time-travel); all events stay within the modeling window and
  any source-specific window (cap, don't bleed past `WINDOW_END`).
- **Subscription renewals bypass web analytics.** Recurring orders are created server-side and
  have no web session, so they must **not** fire GA4 (or ad-platform pixel) web purchase
  events at the web-checkout rate. Model only first orders and one-time repeats as web
  checkouts (~web coverage); include only a small fraction of renewals, and when present
  attribute them **Direct/(not set), never paid**. CRM (Klaviyo/Bloomreach) *does* see
  renewals (server-side order tracking) but must **not** credit auto-renewals as click-driven
  conversions. Subscription *signups* (the customer's first order) are real web checkouts and
  keep their acquisition channel.
- **Channel attribution** is realistically non-uniform — read `channel-mix-benchmarks.md`;
  don't double-count the unattributed baseline.
- **Data issues are the real defect, not a label** (e.g. partial coverage = genuinely missing
  rows). Each issue should match a `validate_raw` check or have a hand-verifiable signature.

## Done = `validate_raw` exits 0

The generator is correct when `python3 -m synthetic_pitch_data.validate_raw --company <slug>`
exits 0 (every check PASS, or a FAIL recorded under `execution_plan.accepted_waivers`). Treat
a FAIL as blocking — fix the generator or the documented targets, don't rationalize it.
