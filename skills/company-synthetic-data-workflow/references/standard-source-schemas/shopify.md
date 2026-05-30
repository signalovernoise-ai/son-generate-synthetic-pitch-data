# Shopify

Use Shopify-aligned source schemas when the company uses Shopify or a Shopify-like export shape.

## Customers

`shopify_customers.csv`

- `id`
- `email`
- `first_name`
- `last_name`
- `phone`
- `created_at`
- `updated_at`
- `state`
- `verified_email`
- `tax_exempt`
- `tags`
- `currency`
- `accepts_marketing`
- `default_address_city`
- `default_address_province`
- `default_address_province_code`
- `default_address_country`
- `default_address_country_code`
- `default_address_zip`

Notes:

- Expect email casing and whitespace drift in some datasets.
- Expect country variants that need normalization.
- `accepts_marketing` may behave like a tri-state in practice when exports are incomplete.

## Orders

`shopify_orders.csv`

- `id`
- `admin_graphql_api_id`
- `order_number`
- `name`
- `customer_id`
- `email`
- `created_at`
- `processed_at`
- `updated_at`
- `currency`
- `presentment_currency`
- `financial_status`
- `fulfillment_status`
- `subtotal_price`
- `total_discounts`
- `total_tax`
- `total_shipping_price_set_amount`
- `total_price`
- `total_line_items_price`
- `taxes_included`
- `total_weight`
- `line_items_count`
- `billing_address_country`
- `billing_address_country_code`
- `billing_address_city`
- `billing_address_province`
- `billing_address_zip`
- `source_name`

Notes:

- Some datasets also include explicit refund fields such as `Refunded Amount` and `Refund Status`.
- Not every Shopify-shaped export contains a real shipping timestamp; `fulfillment_status` is not a substitute for `shipped_at`.
- Duplicate-looking order names can exist even when the final cleaned `id` is unique.

## Order Items

Use this as the standard raw shape when product-level Shopify data is needed.

`shopify_order_items.csv`

- `order_id`
- `line_item_id`
- `admin_graphql_api_id`
- `product_id`
- `variant_id`
- `sku`
- `title`
- `variant_title`
- `vendor`
- `product_type`
- `quantity`
- `price`
- `discounted_price`
- `total_discount`
- `taxable`
- `requires_shipping`
- `fulfillment_status`

Notes:

- If the source only provides nested line items inside orders, document the flattening logic.

## Products

Use this as the standard raw shape when Shopify catalog data is needed.

`shopify_products.csv`

- `product_id`
- `admin_graphql_api_id`
- `title`
- `handle`
- `vendor`
- `product_type`
- `status`
- `published_at`
- `created_at`
- `updated_at`
- `variant_id`
- `sku`
- `barcode`
- `option_1`
- `option_2`
- `option_3`
- `price`
- `compare_at_price`
- `cost`
- `inventory_quantity`

Notes:

- If catalog richness matters to the pitch, include variant-level economics and merchandising fields explicitly.
- When building a company-specific synthetic dataset, anchor the current catalog to the live site wherever possible.
- Use exact current product names, visible prices, and active bundles from the site as the present-day truth set.
- If the site shows promotions such as welcome discounts, subscribe-and-save offers, or bundle pricing, carry those patterns into the modeled product and order history in a sensible way.
- Historic or delisted products can be synthesized, but they should look like realistic predecessors, adjacent variants, or retired bundles rather than unrelated inventions.
