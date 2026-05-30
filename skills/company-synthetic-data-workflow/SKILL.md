---
name: company-synthetic-data-workflow
description: Use this skill when creating or refreshing a company-specific synthetic dataset for a D2C pitch. It guides Codex through gathering company context, browsing the web for current business and tooling signals, confirming source systems with evidence, planning the dataset for user approval, and generating standardized synthetic outputs in the external synthetic_data workspace.
---

# Company Synthetic Data Workflow

Use this skill when the user wants a tailored synthetic dataset for a specific company or brand.

Keep the workflow anchored to the repo at `/Users/julian/Documents/son-generate-synthetic-pitch-data` and the external writable data workspace at `../synthetic_data` unless the user says otherwise.

Do not infer source systems from category norms alone. Only include systems that are confirmed by public evidence, direct user input, or call notes provided by the user.
Default to a modeling window of 18 months of historic data plus 6 months of future data so pitch datasets remain current for longer. Only change this if the user explicitly requests a different time period during setup or plan review.
For high-volume source systems such as CRM, support, or event streams, propose a shorter source-specific window when that keeps the dataset practical while preserving the story. Anchor those shorter extracts back to the core products, orders, and users datasets.
Estimate row volumes before generation. If the proposed raw-source build is likely to exceed a practical threshold, first propose reducing the historic window from 18 months to 12 months, and then scale down operational row volume while preserving the approved business metrics, mix, and trajectories.
Do not use volume controls to shrink low-row-count dimension tables when their impact on total row volume is minimal. Tables such as products, core catalog dimensions, or other small realism-driving reference data should stay as complete as the evidence allows.

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
   - delivery pricing, including any free-delivery threshold or blanket free-shipping policy
   - growth stage, funding, retail footprint, and seasonality clues
   - press releases, investor updates, company filings, and credible reporting that mention revenue, growth, customer trends, or category expansion
   - source systems, vendors, or job-posting evidence of tooling
   - notable retention or acquisition dynamics in the category
Use exact dates when referencing current facts.
Use the exact current product names and prices visible on the company site when building the products table.
You may add a small number of sensible delisted or historic products, but they should remain adjacent to the current catalog rather than invented from scratch.
If current promotions or new-customer discounts are visible, use them explicitly when modeling promotions and historical discount behavior unless the user tells you otherwise.
Capture the free-delivery threshold or delivery-pricing logic explicitly, because it strongly affects AOV and basket behavior.
Use external revenue, growth, and operating signals from press releases, filings, and similar sources to inform the proposed metric trajectories when direct numbers are available or when directional evidence is strong.

3. Create or refresh a company setup file.
Start from `assets/company_setup_template.yaml`. Fill unknown values with explicit assumptions and label them as assumptions.

4. Propose the commercial metric shape before generation.
Before generating any data, define the expected shape of the business over time, including:
   - assumed annual revenue level and annualized growth rates
   - monthly revenue path across the approved window
   - monthly order-volume path across the approved window
   - seasonality pattern with explicit monthly multipliers or directional lifts/drops
   - AOV level and how it changes over time
   - new versus repeat mix over time
   - refund-rate pattern over time
   - retention pattern or repeat-purchase curve over time
   - any expected inflection points such as launches, promotions, migrations, or category expansion, with explicit metric impact
Do not keep these assumptions vague. Quantify them in a way the user can review and challenge before generation starts.
Record these as explicit pre-generation assumptions in the setup artifact and include them in the approval plan.

5. Estimate dataset volume before generation.
Estimate the likely row counts for the raw source outputs, especially:
   - products
   - orders
   - customers
   - order items
   - analytics and attribution event tables
   - CRM or lifecycle event tables
If the projected build is likely to exceed about 5 million total raw rows or otherwise become unwieldy for generation, validation, and review:
   - first propose reducing the historic window from 18 months to 12 months
   - then, if still too large, propose scaling down operational row counts while preserving the approved commercial metrics, growth rates, retention patterns, seasonality, promo effects, and issue prevalence
Apply these reductions primarily to high-volume fact and event tables such as orders, order items, lifecycle events, support events, analytics events, and attribution journeys. Keep low-row-count dimensions such as products as complete as possible.
Do not silently shrink the dataset. Put the proposed reduction into the approval plan for user review.

6. Confirm source systems with evidence.
Only include source systems that are backed by one of:
   - public evidence such as vendor directories, job postings, engineering writeups, or exposed trackers
   - direct user confirmation
   - notes from discovery or sales calls provided by the user
Record the evidence for each system in the setup artifact.
If a system is plausible but unconfirmed, leave it out of generation and list it as an open question instead.

7. Present an execution plan and wait for approval.
Before generating or changing any dataset, present the plan back to the user for review, refinement, and explicit approval.
The plan must include:
   - company brief and modeling scope
   - time window, including whether the default 18 historic months and 6 future months is being used or overridden
   - current catalog and pricing evidence
   - promotion and discount assumptions grounded in current site evidence
   - delivery-pricing assumptions, including the free-delivery threshold if one exists
   - quantified pre-generation metric assumptions and trajectories
   - explicit annual revenue assumptions, annual growth rates, retention levels, AOV levels, refund rates, and the expected effect of promos or seasonality on those metrics
   - confirmed source systems and evidence
   - source schemas to use
   - raw source outputs to build
   - stage outputs and analytics outputs planned for later phases
   - any proposed source-specific window reductions for large datasets
   - estimated raw row counts by dataset
   - any proposed volume controls, including a reduction to 12 historic months and any operational row-count scaling
   - explicit note on which datasets are protected from scaling because they are low-row-count dimensions
   - proposed data-issue mix, including severity, expected prevalence, affected systems, and why each issue belongs in the dataset
   - post-generation validation tests and thresholds
   - generation order and dependencies
   - open questions, constraints, and assumptions
Do not execute generation until the user approves the plan.

8. Select data issues.
Read `references/data-issues-menu.md`, choose only the issues that fit the company and systems, and record:
   - whether the issue is present
   - severity
   - expected prevalence or approximate volume
   - affected systems
   - whether it should be obvious, subtle, or hidden until standardization
   - why it is believable for this company

9. Define downstream outputs without generating them yet.
Read `references/standard-source-schemas/index.md` when selecting platform-specific source tables.
Read `references/standard-stage-schemas/index.md` when planning how source-shaped data will later map into the stage schemas we control.
Read `references/standard-analytics-schemas/index.md` when planning derived analytical outputs that will later be built from stage data.
Do not generate stage or analytics outputs until the raw source datasets have been generated, validated, reviewed, and accepted by the user.

10. Generate data in the external workspace using dependency-aware sequencing.
Keep generated CSVs outside the repo. The Python modules in `synthetic_pitch_data` should read and write in the external `synthetic_data/data/...` tree.
Generate in this order unless the user approves a different dependency model:
   - first generate products using the observed current catalog as the present-day anchor plus a sensible historic and future tail where needed
   - then generate orders as the core commercial timeline
   - then generate customers using the orders output as ground truth where needed
   - only after products, orders, and customers are stable, parallelize dependent raw source datasets such as GA4, Bloomreach, Zendesk, order items, subscription events, or attribution tables
All downstream datasets must reconcile to the same primary and foreign keys, event order, and realistic timestamps unless a selected data issue intentionally introduces a controlled mismatch.

11. Run raw-source post-generation tests.
Execute deterministic validation checks after raw source generation and before any standardization or analytics work.
At minimum, test that:
   - required primary keys are unique in each source dataset where uniqueness is expected
   - foreign keys reconcile across products, orders, customers, order items, and downstream source event tables
   - timestamps are chronologically plausible within and across systems
   - GA4 purchase events align to the corresponding commerce order within a documented tolerance, defaulting to 30 minutes unless the user approves a different threshold
   - downstream support, lifecycle, subscription, and attribution records only reference real core entities and approved source records
   - each source dataset respects its approved time window, including any reduced window for large systems
Record any intentional exceptions that are caused by selected data issues.
Pause for user review after raw-source validation if stage or analytics outputs have not yet been approved for execution.

12. Validate realism and cross-system consistency.
Sense-check revenue, refund rates, country mix, AOV, promotions, and seasonality against the company and category brief.
Also verify that:
   - primary and foreign keys reconcile across systems
   - downstream timestamps are plausible relative to the products, orders, and customers ground truth
   - historic and future records stay within the approved modeling window
   - generated row volumes stay within the approved operational scale for the project
   - the generated time series follows the approved quantified growth, seasonality, AOV, refund, and retention assumptions closely enough to be believable
   - product names, prices, and promotion patterns reflect the observed current site and sensible historical evolution
   - support, lifecycle, and attribution outputs reference real core entities and approved source records
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
- Treat products, then orders, then customers as the core source-generation spine unless the user approves a different dependency model.
- Parallelize only after shared ground-truth entities are generated and locked.
- Keep source generation, stage standardization, and analytics generation as separate approval phases.
- Treat the current site catalog and visible promotions as first-class evidence for product and discount modeling.
- Run explicit post-generation tests before considering the dataset complete.
- Do not write generated CSV outputs into the repo.
