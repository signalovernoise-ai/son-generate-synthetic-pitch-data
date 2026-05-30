# Custom Postgres

Use source-specific schemas when the company has a custom commerce backend.

## Users

`user.csv`

- `user_id`
- `email`
- `first_name`
- `last_name`
- `phone`
- `created_at`
- `updated_at`
- `marketing_opt_in`
- `country`
- `city`
- `postcode`
- `is_active`
- `source`

## Orders

`fact_order.csv`

- `order_id`
- `user_id`
- `order_number`
- `created_at`
- `processed_at`
- `status`
- `order_type`
- `subscription_id`
- `is_first_subscription_order`
- `currency`
- `subtotal`
- `discount_total`
- `tax_total`
- `shipping_total`
- `total`
- `item_count`
- `payment_method`
- `channel`
- `ip_country`

Notes:

- ID-format drift is common in migrated custom systems.
- Orphan orders are possible and should be expected.
- `processed_at < created_at` is a realistic failure mode in messy operational data.
