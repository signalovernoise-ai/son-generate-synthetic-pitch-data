---
name: company-synthetic-data-workflow
description: Use this skill when creating or refreshing a company-specific synthetic dataset for a D2C pitch. It guides Codex through gathering company context, browsing the web for current business and tooling signals, confirming source systems with evidence, planning the dataset for user approval, and generating standardized synthetic outputs in the external synthetic_data workspace.
---

# Company Synthetic Data Workflow

Use this skill when the user wants a tailored synthetic dataset for a specific company or brand.

Keep the workflow anchored to the repo at `/Users/julian/Documents/son-generate-synthetic-pitch-data` and the external writable data workspace at `../synthetic_data` unless the user says otherwise.

Do not infer source systems from category norms alone. Only include systems that are confirmed by public evidence, direct user input, or call notes provided by the user.
Default to a modeling window of 18 months of historic data plus 6 months of future data so pitch datasets remain current for longer. Only change this if the user explicitly requests a different time period during setup or plan review.

## Outcomes

Produce or update:

1. A company setup artifact based on `assets/company_setup_template.yaml`
2. A research-backed business brief using current web sources
3. Raw or source-shaped synthetic datasets by system
4. Standardized stage datasets
5. Standardized analytics datasets
6. A selected set of realistic data issues with severity notes

## Required workflow

1. Gather setup inputs from the user only where needed.
Ask for missing details that materially change the generated data, especially:
   - company name and website
   - geography and currency
   - systems they definitely use or definitely do not use
   - whether this should override the default time window of 18 historic months and 6 future months
   - whether this should model current scale, historic scale, or a target future state

2. Research the company on the web before modeling.
Browse for current information on:
   - category and product mix
   - business model and likely order cadence
   - current product names, product prices, bundles, and likely AOV
   - current promotions, discount banners, welcome offers, and subscription incentives
   - growth stage, funding, retail footprint, and seasonality clues
   - source systems, vendors, or job-posting evidence of tooling
   - notable retention or acquisition dynamics in the category
Use exact dates when referencing current facts.
Use the exact current product names and prices visible on the company site when building the products table.
You may add a small number of sensible delisted or historic products, but they should remain adjacent to the current catalog rather than invented from scratch.
If current promotions or new-customer discounts are visible, use them explicitly when modeling promotions and historical discount behavior unless the user tells you otherwise.

3. Create or refresh a company setup file.
Start from `assets/company_setup_template.yaml`. Fill unknown values with explicit assumptions and label them as assumptions.

4. Confirm source systems with evidence.
Only include source systems that are backed by one of:
   - public evidence such as vendor directories, job postings, engineering writeups, or exposed trackers
   - direct user confirmation
   - notes from discovery or sales calls provided by the user
Record the evidence for each system in the setup artifact.
If a system is plausible but unconfirmed, leave it out of generation and list it as an open question instead.

5. Present an execution plan and wait for approval.
Before generating or changing any dataset, present the plan back to the user for review, refinement, and explicit approval.
The plan must include:
   - company brief and modeling scope
   - time window, including whether the default 18 historic months and 6 future months is being used or overridden
   - current catalog and pricing evidence
   - promotion and discount assumptions grounded in current site evidence
   - confirmed source systems and evidence
   - source schemas to use
   - stage outputs and analytics outputs to build
   - selected data issues and severity
   - post-generation validation tests and thresholds
   - generation order and dependencies
   - open questions, constraints, and assumptions
Do not execute generation until the user approves the plan.

6. Select data issues.
Read `references/data-issues-menu.md`, choose only the issues that fit the company and systems, and record:
   - whether the issue is present
   - severity
   - affected systems
   - whether it should be obvious, subtle, or hidden until standardization

7. Standardize outputs.
Read `references/standard-source-schemas/index.md` when selecting platform-specific source tables.
Read `references/standard-stage-schemas/index.md` when mapping source-shaped data into the stage schemas we control.
Read `references/standard-analytics-schemas/index.md` when defining derived analytical outputs built from stage data.

8. Generate data in the external workspace using dependency-aware sequencing.
Keep generated CSVs outside the repo. The Python modules in `synthetic_pitch_data` should read and write in the external `synthetic_data/data/...` tree.
Generate in this order unless the user approves a different dependency model:
   - first generate orders as the core commercial timeline
   - then generate customers using the orders output as ground truth where needed
   - then generate products using the observed current catalog as the present-day anchor plus a sensible historic tail where needed
   - only after orders, customers, and products are stable, parallelize dependent datasets such as GA4, Zendesk, order items, subscription events, or attribution tables
All downstream datasets must reconcile to the same primary and foreign keys, event order, and realistic timestamps unless a selected data issue intentionally introduces a controlled mismatch.

9. Run post-generation tests.
Execute deterministic validation checks after generation and before delivery.
At minimum, test that:
   - required primary keys are unique in each controlled table
   - foreign keys reconcile across orders, customers, products, order items, and downstream event tables
   - timestamps are chronologically plausible within and across systems
   - GA4 purchase events align to the corresponding commerce order within a documented tolerance, defaulting to 30 minutes unless the user approves a different threshold
   - downstream support, lifecycle, subscription, and attribution records only reference real staged entities
Record any intentional exceptions that are caused by selected data issues.

10. Validate realism and cross-system consistency.
Sense-check revenue, retention, refund rates, country mix, AOV, and seasonality against the company and category brief.
Also verify that:
   - primary and foreign keys reconcile across systems
   - downstream timestamps are plausible relative to the orders and customers ground truth
   - historic and future records stay within the approved modeling window
   - product names, prices, and promotion patterns reflect the observed current site and sensible historical evolution
   - support, analytics, lifecycle, and attribution outputs reference real staged entities
If the numbers or joins feel too generic or inconsistent, revise before delivering.

## Files to read when needed

- `references/setup-checklist.md`: step-by-step setup and research checklist
- `references/data-issues-menu.md`: menu of common real-world data issues
- `references/standard-source-schemas/index.md`: platform-specific source extract schemas
- `references/standard-stage-schemas/index.md`: canonical stage schemas and mapping guidance
- `references/standard-analytics-schemas/index.md`: canonical analytics schemas derived from stage data

## Repo commands

Use these commands from the repo root when useful:

```bash
python3 -m synthetic_pitch_data.run_all
python3 -m synthetic_pitch_data.monthly_cohort_retention
```

## Working style

- Prefer browsing current primary sources when facts may have changed.
- Make assumptions explicit and keep them editable.
- Keep the company-specific setup artifact as the single source of truth for generation choices.
- Treat source-system confirmation as evidence-based, not inferential.
- Always stop for plan review and explicit approval before execution.
- Parallelize only after shared ground-truth entities are generated and locked.
- Treat the current site catalog and visible promotions as first-class evidence for product and discount modeling.
- Run explicit post-generation tests before considering the dataset complete.
- Do not write generated CSV outputs into the repo.
