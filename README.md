# son-generate-synthetic-pitch-data

This repo now owns the code and workflow for building company-specific synthetic datasets for pitch demos, while keeping generated CSVs in the sibling workspace at `../synthetic_data`.

## Data workspace

By default the generators read and write from:

- `../synthetic_data/data/src`
- `../synthetic_data/data/stage`
- `../synthetic_data/data/analytics`

Override that location with `SYNTHETIC_DATA_HOME=/absolute/path/to/synthetic_data`.

## Python modules

The imported generators live in [`synthetic_pitch_data`](./synthetic_pitch_data). Company-specific generators are grouped under [`synthetic_pitch_data/company`](./synthetic_pitch_data/company), while shared helpers stay in the package root. Run everything with:

```bash
python3 -m synthetic_pitch_data.run_all
```

That command stages the example source datasets and rebuilds monthly cohort retention outputs in the external synthetic-data workspace.

If you need reproducible retention outputs, pin the as-of date:

```bash
RETENTION_AS_OF_DATE=2026-05-30 python3 -m synthetic_pitch_data.run_all
```

## Skill scaffold

The first pass of the reusable Codex workflow lives in [`skills/company-synthetic-data-workflow`](./skills/company-synthetic-data-workflow). It is designed to:

- gather company-specific setup inputs
- browse the web to build a realistic business brief
- choose source systems and schema mappings
- select and tune realistic data issues
- standardize outputs into common downstream schemas

## Current standard outputs

The imported scripts currently standardize to:

- `users.csv`: `user_id`, `created_at`, `country`
- `orders.csv`: `order_id`, `user_id`, `ordered_at`, `shipped_at`, `net_sale_price`, `country`
- `monthly_cohort_retention.csv`: `first_order_month`, `months_since_first_order`, `brand`, `total_cohort_users`, `retained_users`, `retention_rate`
