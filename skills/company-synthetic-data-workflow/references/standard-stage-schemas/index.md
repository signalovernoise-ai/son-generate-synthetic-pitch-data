# Standard Stage Schemas

Use this folder for the stage schemas that we define and control after cleaning and standardization.

These schemas are canonical. Source-specific extracts should map into these shapes in a documented and repeatable way.

Read the file for the relevant stage output:

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
