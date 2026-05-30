# Core Users

`users.csv`

Canonical stage table for one row per person or account-level customer record after identity cleanup within a company dataset.

## Grain

One row per standardized user.

## Required fields

- `user_id`: canonical user identifier used across stage and analytics outputs
- `created_at`: first known account creation timestamp in UTC ISO 8601 format
- `country`: normalized country code or best-available country value

## Rules

- Preserve prospects or leads if they are valid customer records in the source systems, even when they have no orders yet.
- Do not duplicate rows for one customer because of multi-system source IDs. Resolve source IDs upstream and retain the canonical user row here.
- Leave marketing, consent, lifecycle, or subscription detail in source-specific tables until we define separate controlled stage schemas for those domains.
