# Core Orders

`orders.csv`

Canonical stage table for one row per commercial order after source-level cleaning, filtering, and net revenue standardization.

## Grain

One row per standardized order.

## Required fields

- `order_id`: canonical order identifier used across stage and analytics outputs
- `user_id`: canonical foreign key to `core-users`
- `ordered_at`: order creation or placement timestamp in UTC ISO 8601 format
- `shipped_at`: trustworthy shipment timestamp in UTC ISO 8601 format, or null if unavailable
- `net_sale_price`: post-refund merchandise revenue for the order in dataset currency
- `country`: normalized shipping or customer country based on the documented fallback order

## Rules

- Exclude obvious test, QA, internal, staging, and failed payment rows unless the dataset intentionally includes them as a documented issue.
- Use a netted order value where refunds are known. If the source only partially exposes refunds, keep the best available net figure and document the limitation.
- Keep one row per order in this table. Order-line or SKU detail belongs in source-specific tables until we define a controlled stage order-items schema.
- Preserve the canonical `user_id` even where the source order originally arrived as guest checkout or with a migrated legacy ID.
