# Skio

Use Skio as the standard subscription source for Shopify brands whose recurring billing runs on
Skio. It plays the same role in the dataset as Recharge (`recharge.md`) and OrderGroove
(`ordergroove.md`) — pick **one** subscription system per company, not several, unless evidence
shows a genuine migration.

Detection: the `skio-subscriptions-yc-s20` Shopify app extension in the rendered storefront
(`cdn.shopify.com/extensions/<uuid>/subscriptions-<n>/assets/skio-referrals.js` and `.css`), a
`SkioReferralBanner` element, a `/tools/skio` or Skio-hosted customer portal, or Skio in the
store's installed-app list. Skio also ships a referral programme, so the referral banner is
often the first thing visible.

Important:

- Skio is built on **Shopify's native Subscription Contracts API**, not a parallel checkout. This
  differs from Recharge, which historically ran its own checkout. Consequences that matter for
  the data:
  - The subscription is a Shopify subscription contract, so `shopify_subscription_contract_id` is
    a real identifier and the selling plan on the Shopify order line is the authoritative cadence.
  - A successful billing attempt creates a real Shopify order, so
    `skio_subscription_orders.shopify_order_id` is a genuine foreign key into `shopify_orders.id`.
    Do not model Skio orders as a parallel commerce universe.
- This linkage is what makes the **"renewals bypass web analytics"** gap provable: recurring
  billing attempts are processed server-side with no browser session, so they never fire a GA4 (or
  ad-platform) web purchase event. See `generator-contract.md`.
- **A subscription is not a billing attempt.** `skio_subscriptions.csv` is the standing agreement
  (one row per subscribed line, with its cadence); `skio_subscription_orders.csv` is the billing
  event stream. A subscription has many billing attempts.
- **Identifiers are UUID strings**, not integers — e.g.
  `3f6c1b2a-9d41-4e0a-9b77-6c2f5a1e8d33`. This is the most visible shape difference from Recharge
  and OrderGroove and it is worth preserving: a warehouse that types subscription ids as BIGINT
  breaks on a Skio migration. Shopify-side ids (`shopify_customer_id`, `shopify_order_id`,
  `shopify_variant_id`) stay numeric so they join to the commerce spine.
- **Enums are UPPER_SNAKE_CASE** (`ACTIVE`, `CANCELLED`, `SUCCEEDED`, `CARD_DECLINED`), again
  unlike Recharge's lowercase values. Keep them source-shaped; the stage layer normalises.
- `status` on a subscription is `ACTIVE` / `PAUSED` / `CANCELLED` / `EXPIRED`. `cancelled_at`
  records when the customer acted in the portal, which routinely lags the final successful billing
  attempt — do not treat it as the churn date without checking the last attempt.
- Cadence lives in the **selling plan**: `selling_plan_id`, `selling_plan_name`, plus an explicit
  `billing_interval_unit` / `billing_interval_count` and `delivery_interval_unit` /
  `delivery_interval_count`. Prepaid plans bill less often than they deliver, so keep both pairs.
- Prices are per unit in the presentment currency and are the **discounted** subscription price
  (list price minus the selling plan's percentage adjustment), not the one-time list price.

## Subscriptions

One row per subscribed line item (a customer subscribed to two products has two rows).

`skio_subscriptions.csv`

- `id`
- `platform_customer_id`
- `shopify_customer_id`
- `shopify_subscription_contract_id`
- `status`
- `created_at`
- `updated_at`
- `cancelled_at`
- `cancellation_reason`
- `paused_at`
- `next_billing_date`
- `selling_plan_id`
- `selling_plan_name`
- `selling_plan_discount_percentage`
- `billing_interval_unit`
- `billing_interval_count`
- `delivery_interval_unit`
- `delivery_interval_count`
- `quantity`
- `price`
- `presentment_currency`
- `product_title`
- `variant_title`
- `sku`
- `shopify_product_id`
- `shopify_variant_id`
- `is_prepaid`
- `swap_count`
- `skip_count`

Notes:

- `id` is the Skio subscription UUID and is the primary key.
- `shopify_customer_id` is the foreign key to `shopify_customers.id`. `platform_customer_id` is
  Skio's own customer UUID — carry both, because brands join on either depending on the tool.
- `cancellation_reason` is a picklist value from Skio's cancellation flow (`TOO_EXPENSIVE`,
  `TOO_MUCH_PRODUCT`, `FOUND_ALTERNATIVE`, `QUALITY`, `OTHER`, blank). Keep it source-shaped.
- `next_billing_date` is blank once the subscription is cancelled or expired.
- `swap_count` and `skip_count` are Skio-native retention levers (swap the product, skip a
  delivery). A high `skip_count` before cancellation is a real pre-churn signal and is worth
  keeping; it has no Recharge equivalent.
- `billing_interval_*` equals `delivery_interval_*` on a standard plan and differs only when
  `is_prepaid` is true.

## Subscription orders (billing attempts)

One row per billing attempt. This is the grain that reconciles to commerce.

`skio_subscription_orders.csv`

- `id`
- `subscription_id`
- `platform_customer_id`
- `shopify_customer_id`
- `shopify_order_id`
- `origin`
- `status`
- `error_code`
- `scheduled_at`
- `processed_at`
- `created_at`
- `updated_at`
- `subtotal_price`
- `total_discounts`
- `total_tax`
- `shipping_price`
- `total_price`
- `currency`
- `attempt_number`
- `next_retry_at`
- `tags`

Notes:

- `origin` is `CHECKOUT` for the order that started the subscription and `RECURRING` for every
  renewal. The first-order/renewal split is exactly this field — do not re-derive it.
- `status` is `SUCCEEDED` / `FAILED` / `QUEUED` / `SKIPPED` / `REFUNDED`. Only `SUCCEEDED` rows
  carry a `shopify_order_id`; `FAILED`, `QUEUED` and `SKIPPED` rows legitimately have none, so the
  foreign key is **sparse by design** rather than broken.
- `error_code` is populated only on `FAILED` rows (`CARD_DECLINED`, `EXPIRED_PAYMENT_METHOD`,
  `INSUFFICIENT_FUNDS`, `PROCESSING_ERROR`). It is blank everywhere else — a genuine
  meaningful-blank field, not a data-quality problem.
- `attempt_number` above 1 with a populated `next_retry_at` is the signature of dunning retries,
  which is where duplicate-looking orders come from in a subscription store.
- Money fields follow the Shopify conventions in `metric-definitions.md`: VAT-inclusive where VAT
  applies, and `shipping_price` is carried separately so it stays out of AOV.

## Standardised stage view

The stage cleaner conforms these to the shared `subscriptions` and `subscription_orders` roles
alongside the Recharge and OrderGroove specs, so a downstream retention or churn model does not
need to know which subscription platform a client runs. The two Skio-specific normalisations are
lowercasing the UPPER_SNAKE enums and mapping `origin` `CHECKOUT`/`RECURRING` onto the canonical
`checkout`/`recurring` values.
