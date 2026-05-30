# Monthly Cohort Retention

`monthly_cohort_retention.csv`

Canonical analytics table for repeat-purchase retention by first-order month.

## Grain

One row per `first_order_month` x `months_since_first_order`.

## Required fields

- `first_order_month`: month of the customer's first known order, expressed as the first calendar day of that month
- `months_since_first_order`: integer month offset from the first order, starting at `1`
- `brand`: company or dataset identifier
- `total_cohort_users`: number of customers in the cohort who have matured far enough to be eligible for this retention month
- `retained_users`: number of eligible cohort users with at least one later order in that retention month
- `retention_rate`: `retained_users / total_cohort_users`, expressed as a decimal from `0` to `1`

## Rules

- Build from the standardized stage orders table, not directly from source extracts.
- Define cohorts from the first valid order per user.
- Exclude month `0`. This output measures repeat retention only.
- Apply maturity logic so recent cohorts are only counted where enough time has elapsed to observe the retention month.
- Keep cohort sizing and retention logic consistent across companies so differences reflect the business profile, not schema drift.
