# Metric Definitions

Single source of truth for how every headline metric is **defined and computed** in this
workflow. The setup yaml carries the *targets*; this file fixes the *formulas* so that the
generator, the validation harness, and the pitch narrative all mean the same thing. When a
metric in the setup yaml is ambiguous, this file wins.

All money figures are in the company's reporting `currency`. Monetary metrics are computed on
the standard `shopify_orders.csv` / `shopify_order_items.csv` source shapes.

## Order-value conventions

These three choices resolve the ambiguity that otherwise causes silent ~10% metric drift:

- **Discounts:** all per-order metrics are **net of discount**. `total_price` already has
  `total_discounts` removed. Never calibrate order size against `compare_at_price` /
  `total_line_items_price` (the gross list value) and then report `total_price` — that
  systematically undershoots the AOV target by the blended discount rate.
- **VAT / tax:** prices are **VAT-inclusive** (`taxes_included = true`). `total_price` is the
  gross amount the customer pays; `total_tax` is a component *within* it, not added on top.
- **Shipping:** **excluded** from AOV and revenue. Model the company's real delivery policy
  (e.g. blanket free UK delivery → `shipping = 0`). If a free-delivery threshold exists,
  capture it because it bunches baskets just above the floor.

## Metric formulas

| Metric | Formula | Notes |
|---|---|---|
| **AOV** | `mean(total_price)` over orders in the period | net of discount, VAT-incl, shipping-excl |
| **Revenue** (gross sales) | `sum(total_price)` over orders in the period | matches `revenue_by_period`; gross of refunds |
| **Net revenue** | `sum(total_price - refunded_amount)` | use only where explicitly labelled "net" |
| **Order volume** | `count(orders)` in the period | see promo convention below |
| **Refund rate** | `count(orders with refunded_amount > 0) / count(orders)` | by order, not by value |
| **Subscription share** | `count(orders with a subscription/selling-plan line) / count(orders)` | order-level, not line-level |
| **New vs repeat share** | `new = count(first order for that customer) / count(orders)`; `repeat = 1 - new` | first-order detection by earliest `created_at` per customer |
| **Retention (mₙ)** | share of a first-order cohort with an order in month n after first order | matches `retention_checkpoints` |

When the generator applies a behavioural multiplier on top of a target (e.g. a per-category
subscription uplift), the **realized** value — not the nominal target — is what the validation
harness measures. Keep multipliers small enough that the realized value still lands inside the
target's tolerance band.

## Promotions and monthly volume (convention)

**Monthly volume targets already include promotional uplift.** Promotions in D2C lean into key
trading periods, so the `orders_by_period` path is the *final, promo-inclusive* truth, not a
clean baseline that promos add to.

Consequences:

- The generator must hit `orders_by_period` **exactly** (within tolerance). Do **not** add a
  separate intra-month volume lift on top of a promo window — that would double-count.
- Seasonality multipliers and promo-period demand are already baked into the monthly numbers.
- Promotions still shape **within-month behaviour**: lower realized AOV during the discount
  window, higher new-subscription starts, a promo-acquired cohort with different repeat
  behaviour. Validate promo effects on **AOV / mix**, not on total monthly volume.

If a future company instead wants monthly targets to be *pre-promo baselines* that promos lift
above, state that explicitly in the setup yaml `execution_plan` and override this convention
there.

## The order-mix identity (check this before generating)

New/repeat share, subscription share and the retention curve are **not independent** — they
are three views of the same order population. Quoting them from intuition produces a set that
cannot be generated. Before writing any targets into the setup yaml, check they solve:

```
1 = new_share × (1 + take_rate × renewals_per_subscriber) + adhoc_repeat_share
subscription_order_share = new_share × take_rate × (renewals_per_subscriber + 1)
repeat_order_share       = 1 − new_share
retention(first renewal) ≈ take_rate × first-renewal survival + adhoc floor
```

where `take_rate` is the share of first orders that start a subscription and
`renewals_per_subscriber` is the sum of cumulative survival across renewal cycles.

If the identity does not balance, renewal *demand* will exceed the renewal *capacity* the
monthly order targets leave free, the generator will skip renewals every month to hit its
counts, and the retention curve will come out flatter and smeared versus the documented
checkpoints. Fix the assumptions, not the generator.

## Estimating the first-renewal checkpoint (discount it by the interval mix)

A recurring pre-generation miss: estimating `m1` as `take_rate × first-renewal survival` and
then finding the realized curve roughly half that. The error is forgetting that **a
subscriber on a 3- or 6-month interval cannot renew at m1**. Only the 1-month cohort can.

```
retention(m1) ≈ take_rate × share_on_1_month_interval × first-renewal survival + adhoc floor
retention(mN) ≈ take_rate × share_on_N_month_interval × survival to that cycle + adhoc floor
```

So a catalog sold as 1 / 3 / 6-month supplies produces a **cadence-shaped** curve with peaks
at m1, m3 and m6, not a smooth decay — and `m3` can legitimately read **above** `m1` when the
1-month cohort decays fast while the 3-month cohort arrives intact. Estimate each checkpoint
against the interval mix before writing it into the setup artifact, and expect to replace all
of them with realized values after generation.

## Check the order-mix identity against the generator's parameters, not in the abstract

Solving the identity on paper is not enough. The numbers that have to balance are the ones
the generator will actually use — `take_rate`, per-cycle `RENEWAL_SURVIVAL`,
`adhoc_repeat_share`, `MIN_NEW_SHARE` and the renewal-capacity cap. Before generating, compute
the implied shares from those constants and compare them to the documented mix:

```
renewal_order_share ≈ new_share × take_rate × renewals_per_subscriber
                      where renewals_per_subscriber = Σ cumulative survival across cycles
repeat_order_share  ≈ renewal_order_share + adhoc_repeat_share
```

If the implied share and the documented target disagree, fix the constants *or* the target
before generating. Discovering it afterwards costs a full regeneration, and right-censoring at
the window end will additionally hold the final half-year below its target no matter what the
constants say — expect that and do not tune it away.

## Retention: two definitions, do not mix them

- **Calendar-month offset** — cohort month vs order month. What most brands mean by "month 1".
- **Elapsed 30-day buckets** from the exact first-order timestamp. What
  `monthly_cohort_retention` computes, and what most warehouse implementations do.

For a subscription brand on a fixed cadence the two differ materially: a renewal ~30 days
after the first order lands in bucket 0 or 1 depending on a few days of jitter, and bucket 0
is discarded, so the elapsed-days curve reads systematically lower at every cadence peak.
State which definition a documented checkpoint uses, and never put both in one chart.

## Scaling

When operational row counts are scaled (`volume_plan.reduction_actions.row_volume_scaling_factor`),
every volume and revenue target is multiplied by the scaling factor before comparison; **ratios
and rates (AOV, refund rate, subscription share, retention) are scale-invariant** and compared
to the unscaled target. Protected dimensions (e.g. `products`) are never scaled.
