# Recharge

Use Recharge (Recharge Payments) as the standard subscription source for Shopify brands whose
recurring billing runs on Recharge. It plays the same role in the dataset as OrderGroove
(`ordergroove.md`) does for brands on that platform — pick one subscription system per company,
not both, unless evidence shows a genuine migration.

Detection: `checkout.rechargeapps.com` in the storefront's checkout-domain configuration, a
Recharge customer portal on the brand's domain, or the Recharge app in the store's installed-app
list.

Important:

- Recharge sits **on top of** Shopify. A recurring charge creates a real Shopify order, so
  `recharge_subscription_orders.shopify_order_id` is a genuine foreign key into
  `shopify_orders.id`. Do not model Recharge orders as a parallel commerce universe.
- This linkage is what makes the **"renewals bypass web analytics"** gap provable: recurring
  charges are processed server-side with no browser session, so they never fire a GA4 (or ad
  platform) web purchase event. See `generator-contract.md`.
- **A subscription is not a charge.** `recharge_subscriptions.csv` is the standing agreement (one
  row per subscribed line, with its cadence); `recharge_subscription_orders.csv` is the billing
  event stream. A subscription has many charges.
- `status` on a subscription is `active` / `cancelled` / `expired`. `cancelled_at` records when the
  customer acted in the portal, which routinely lags the final successful charge — do not treat it
  as the churn date without checking the last charge.
- Cadence is expressed twice: `order_interval_unit` (`day` / `week` / `month`) with
  `order_interval_frequency`, and `charge_interval_frequency` for prepaid plans where several
  deliveries are billed together. Keep both.
- Prices are per unit in the presentment currency and are the **discounted** subscription price,
  not the one-time list price.

## Subscriptions

One row per subscribed line item (a customer with two subscribed products has two rows).

`recharge_subscriptions.csv`

- `id`
- `customer_id`
- `shopify_customer_id`
- `address_id`
- `status`
- `created_at`
- `updated_at`
- `cancelled_at`
- `cancellation_reason`
- `next_charge_scheduled_at`
- `order_interval_unit`
- `order_interval_frequency`
- `charge_interval_frequency`
- `order_day_of_month`
- `quantity`
- `price`
- `presentment_currency`
- `product_title`
- `variant_title`
- `sku`
- `shopify_product_id`
- `shopify_variant_id`
- `is_prepaid`
- `is_skippable`

Notes:

- `id` is the Recharge subscription id and is the primary key.
- `shopify_customer_id` is the foreign key to `shopify_customers.id`. `customer_id` is Recharge's
  own customer id — carry both, because brands join on either depending on the tool.
- `cancellation_reason` is a short free-text or picklist value; keep it source-shaped.
- `next_charge_scheduled_at` is blank once the subscription is cancelled or expired.

## Subscription orders (charges)

One row per billing attempt. This is the grain that reconciles to commerce.

`recharge_subscription_orders.csv`

- `id`
- `subscription_id`
- `customer_id`
- `shopify_customer_id`
- `shopify_order_id`
- `type`
- `status`
- `scheduled_at`
- `processed_at`
- `created_at`
- `updated_at`
- `total_line_items_price`
- `subtotal_price`
- `total_discounts`
- `total_tax`
- `shipping_price`
- `total_price`
- `currency`
- `number_times_tried`
- `retry_date`
- `tags`

Notes:

- `type` is `checkout` for the order that started the subscription and `recurring` for every
  renewal. The first-order/renewal split is exactly this field — do not re-derive it.
- `status` is `success` / `error` / `queued` / `skipped` / `refunded`. Only `success` rows carry a
  `shopify_order_id`; `error` and `skipped` rows legitimately have none, so the foreign key is
  sparse by design rather than broken.
- `number_times_tried` above 1 with a populated `retry_date` is the signature of dunning retries,
  which is where duplicate-looking orders come from in a subscription store.
- Money fields follow the Shopify conventions in `metric-definitions.md`: VAT-inclusive where VAT
  applies, and `shipping_price` is carried separately so it stays out of AOV.

## Standardised stage view

The stage cleaner conforms these to the shared `subscriptions` and `subscription_orders` roles
alongside the OrderGroove specs, so a downstream retention or churn model does not need to know
which subscription platform a client runs.
