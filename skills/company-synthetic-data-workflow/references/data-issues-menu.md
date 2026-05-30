# Data Issues Menu

Use this as a menu, not a checklist. Choose the smallest believable set that makes the dataset feel real.

## Identity and joining

- Duplicate customer records across systems
- Guest checkout users not linked back to CRM profiles
- Different IDs for the same customer between commerce and lifecycle tools
- Email casing or whitespace inconsistencies
- Missing user IDs on historic orders
- User ID format drift after migrations or legacy-system merges
- Duplicate-looking display IDs even when the underlying row ID is unique
- Orphaned orders or events whose user ID no longer resolves to a customer record
- Valid prospects or leads present in customer tables with no orders yet

## Orders and revenue

- Refunded orders zeroed out in one export but netted in another
- Partially refunded orders represented as full refunds
- Partial refunds flagged in status but missing an explicit refund amount
- Shipping included in gross sales in one system and excluded in another
- Cancelled orders mixed with completed orders
- Near-duplicate orders caused by retries or replayed webhooks
- Implausible values such as 0.01 test orders or very large outlier totals
- Pending or failed orders mixed into transactional extracts
- Subscription discount logic changing AOV or retention after a product launch
- Test orders created through 100% discount codes, zero-total checkouts, or negative-value rows
- Timestamp reversals such as `processed_at` before `created_at`
- Explicit staging-channel orders mixed into production-looking transactional extracts
- Rapid order bursts within seconds that suggest load tests or duplicated ingestion
- Duplicate heuristics that are platform-specific, for example same email and total within minutes or same user and total within seconds

## Marketing and attribution

- UTM gaps on paid social traffic
- Channel bucketing drift over time
- Meta or Google spend lagging by one to three days
- Campaign naming inconsistencies across ad accounts
- Blended CAC understated because affiliate spend is missing

## Lifecycle and CRM

- Suppressed or unsubscribed users still present in sends exports
- Klaviyo profiles missing acquisition source
- Subscription churn events delayed relative to billing events
- Legacy segments using stale definitions
- Leads or prospects present in customer tables with no orders
- Marketing-consent fields behaving like tri-state booleans because blanks are meaningful

## Analytics and event tracking

- GA4 purchase counts not matching commerce orders
- Missing device or landing-page fields on older sessions
- Bot or internal traffic leakage
- Session-to-order joins unavailable for a subset of orders
- Event volume drops around consent or tag-manager changes
- Cohort retention shifts that are caused by customer-mix changes rather than true within-segment behavior

## Operations and support

- Country inferred from IP in one system and shipping address in another
- Fulfillment timestamps missing for a subset of orders
- Support tickets not consistently linked to orders or customers
- Return reasons free-text only
- Staging contamination from explicit channels, internal sources, or test email patterns
- Free-delivery threshold effects causing order values to bunch just above the shipping floor
- Delivery-policy changes that alter AOV and item-count behavior over time

## Warehouse and schema quality

- Column renamed partway through the history
- Enum values changing over time
- Enum casing drift such as `GBP` vs `gbp`
- Type drift between extracts
- Sparse backfills for one source
- Late-arriving data changing recent periods
- A field being present for one platform export but absent in another export of the same platform
- Missing fields that can only be recovered from another source or a documented fallback rule
- Source exports that expose status-based refund signals but not refund amounts

## Severity scale

- `low`: noticeable but not analysis-breaking
- `medium`: materially affects some metrics or joins
- `high`: likely to trigger incorrect conclusions unless standardized
