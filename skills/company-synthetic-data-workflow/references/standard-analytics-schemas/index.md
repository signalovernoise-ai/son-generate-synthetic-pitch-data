# Standard Analytics Schemas

Use this folder for derived analytical outputs that we define and control after stage standardization.

These schemas should be built from the controlled stage layer, not directly from raw source extracts.

Read the file for the relevant analytics output:

- `monthly-cohort-retention.md`

## Modeling Guidance

- Keep business logic, cohort definitions, attribution windows, and maturity rules explicit.
- Include only analytics fields that are stable enough to compare across companies.
- Where a metric depends on an assumption, such as refund treatment or cohort maturity, document the rule in the schema file and the company setup artifact.
