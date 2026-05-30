# Standard Stage Schemas

Use this folder for the stage schemas that we define and control after cleaning and standardization.

## Current canonical stage model

The stage layer is produced by the `synthetic_pitch_data/staging` package (see
`../stage-cleaning.md` for the methodology and detector battery). For each company it
writes one cleaned table per produced extract under `data/stage/<slug>/`, where:

- the **commerce spine** (`shopify_customers`, `shopify_orders`, `shopify_order_items`,
  `shopify_products`) is standardized to the **Shopify shape** — a non-Shopify backend is
  conformed by an adapter first. Cleaning derives `net_sale_price` (refund-netted) on
  orders and `is_subscription` (selling-plan presence) on order items.
- **non-commerce systems** (GA4, Bloomreach, Zendesk, OrderGroove, Triple Whale) are
  cleaned within their own standard source schemas (see `../standard-source-schemas/`).

Analytics read these cleaned stage tables directly (e.g. retention reads
`shopify_orders.csv`). The `core-users` / `core-orders` fields below remain the canonical
*logical* commerce fields and their mapping from the Shopify shape:

- `user_id` ← `shopify_customers.id` / `shopify_orders.customer_id`
- `order_id` ← `shopify_orders.id`; `ordered_at` ← `created_at`; `net_sale_price` derived

Read the file for the relevant logical mapping:

- `core-users.md`
- `core-orders.md`

## Mapping Guidance

- Preserve raw source-shaped extracts separately from standardized stage outputs.
- Standardize timestamps to UTC ISO 8601 where possible.
- Preserve leads or prospects with valid account creation timestamps even if they have no orders.
- Use `net_sale_price` for post-refund order value in standardized order tables.
- If a source only exposes partial refunds via status but not amount, document the netting limitation explicitly.
- Set `shipped_at` to null when the source does not expose a trustworthy shipment timestamp.
- Keep country as the best available normalized country code or country string, but document the source of truth and fallback order.
- When a source lacks a canonical field, record the imputation or fallback rule in the company setup artifact.
- Keep analytics-only aggregates, cohorts, and attribution outputs out of the stage layer. Define those separately under `standard-analytics-schemas`.
