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
   - whether the brand's peak trading windows run on a non-Gregorian calendar (Ramadan/Eid, Lunar New Year, Diwali) — read `references/seasonality-calendars.md` when they do, because those peaks migrate across Gregorian months and break year-on-year month comparison
   - for UK private companies, Companies House filings — where accounts are filed without a profit and loss account, the corporation-tax creditor, the movement in retained earnings and closing stock still bound revenue (see `references/setup-checklist.md`)
As a standard step for every client, run a website technology-profiler check (e.g. BuiltWith, Wappalyzer, or the brand's on-site JavaScript/script tags and DNS/email headers) to detect the actual martech, analytics, subscription, and CRM/ESP stack in use. Treat this as the default first pass for source-system evidence — especially for the campaign/email-SMS system (Klaviyo vs Bloomreach vs Customer.io, etc.), where category norms are a weak signal and the live site usually reveals the truth. Record what the profiler detects (and what it does not) in the setup artifact, and reconcile it explicitly against any call-note or user-stated tooling.
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
   - seasonality pattern with explicit monthly multipliers, plus an explicit statement of whether seasonality is applied as a separate multiplier layer or baked into the monthly volume path — do not record multipliers in the setup artifact that the generator does not actually apply
   - AOV level and how it changes over time
   - new versus repeat mix over time
   - refund-rate pattern over time
   - retention pattern or repeat-purchase curve over time
   - any expected inflection points such as launches, promotions, migrations, or category expansion, with explicit metric impact
Do not keep these assumptions vague. Quantify them in a way the user can review and challenge before generation starts.
Record these as explicit pre-generation assumptions in the setup artifact and include them in the approval plan.
Check the proposed mix against the order-mix identity in `references/metric-definitions.md` before writing it into the setup artifact. New/repeat share, subscription share and the retention curve are three views of one order population; a set quoted from intuition usually cannot be generated, and the mismatch only surfaces after generation as a flattened retention curve.
Read `references/metric-definitions.md` and follow it for how every metric is computed. In particular: AOV and revenue are net of discount, VAT-inclusive, and shipping-excluded; calibrate order size against the net price the customer pays, never the gross list/`compare_at_price` value. Monthly order-volume targets are promo-inclusive — promotions lean into key trading periods, so they are already baked into the monthly path; model promo effects on AOV and mix, not as an additional volume lift on top of the monthly target. If a company instead wants pre-promo baselines, state that override in the setup artifact.

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
Reverse that order only when the history itself carries the story — a long replenishment or subscription cadence needs the full 18 months to show a cohort curve at all, and a window cut that still leaves the build over threshold buys nothing. When you reverse it, say so explicitly in the approval plan with the reasoning, and let the user decide.
Estimate order-item rows from the actual basket model, not a generic lines-per-order multiplier: a "pack" SKU is one line, so a multi-unit brand can still average close to one line per order.
Apply these reductions primarily to high-volume fact and event tables such as orders, order items, lifecycle events, support events, analytics events, and attribution journeys. Keep low-row-count dimensions such as products as complete as possible.
Do not silently shrink the dataset. Put the proposed reduction into the approval plan for user review.

6. Confirm source systems with evidence.
Only include source systems that are backed by one of:
   - public evidence such as vendor directories, job postings, engineering writeups, or exposed trackers
   - a website technology-profiler result (BuiltWith / Wappalyzer / on-site script and header inspection) — run this as standard for every client
   - a **public ad-library result** for paid-media systems (Meta Ad Library, TikTok Commercial Content Library), searchable by advertiser and region
   - direct user confirmation
   - notes from discovery or sales calls provided by the user
**A missing pixel is not evidence of absence for paid media.** On Shopify, the Meta, TikTok and Google pixels run inside the server-side web-pixels sandbox, so `connect.facebook.net` / `analytics.tiktok.com` will not appear in the rendered page source even when the channel is the brand's largest. `webPixelsConfigList` lists installed app pixels but does not name them. Always check the ad libraries before excluding a paid-social channel — excluding a live channel understates acquisition far more than including a dormant one.
Record the evidence for each system in the setup artifact.
When a profiler result and a call note or user belief disagree on a system (e.g. the site shows Klaviyo but notes say Customer.io), surface the conflict in the plan and let the user resolve it rather than silently picking one.
If a system is plausible but unconfirmed, leave it out of generation and list it as an open question instead.

7. Present an execution plan and wait for approval.
Before generating or changing any dataset, present the plan back to the user for review, refinement, and explicit approval.
The plan must include:
   - company brief and modeling scope
   - time window, including whether the default 18 historic months and 6 future months is being used or overridden
   - current catalog and pricing evidence
   - promotion and discount assumptions grounded in current site evidence
   - delivery-pricing assumptions, including the free-delivery threshold if one exists
   - quantified pre-generation metric assumptions and trajectories, shown in the approval message itself as an explicit month-by-month table (revenue, orders, AOV, and the seasonality multiplier or note per month) — not only inside the setup artifact, so the user can review and challenge the actual numbers
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
Give every selected issue a measurable definition of done so it can be verified, not just asserted. Where a registered validation check exists (see step 11), record its `check` name and an `expected_prevalence_range` in the setup artifact; for issues with no automated check, write a concrete signature an analyst could confirm by hand.
Model data issues as the real defect, not a cosmetic label. For example, "partial attribution coverage" means orders genuinely missing from the attribution source (fewer rows), not just a channel value set to unattributed. When modelling acquisition channels and attribution, read `references/channel-mix-benchmarks.md` so the channel mix is realistically non-uniform and the unattributed baseline is not accidentally doubled by stacked code paths.

9. Define downstream outputs without generating them yet.
Read `references/standard-source-schemas/index.md` when selecting platform-specific source tables.
Read `references/standard-stage-schemas/index.md` when planning how source-shaped data will later map into the stage schemas we control.
Read `references/standard-analytics-schemas/index.md` when planning derived analytical outputs that will later be built from stage data.
Do not generate stage or analytics outputs until the raw source datasets have been generated, validated, reviewed, and accepted by the user.

10. Generate data in the external workspace using dependency-aware sequencing.
Read `references/generator-contract.md` before writing or extending a company's `generate_raw.py`. It is the authoring contract — structure, conventions, shared helpers, AOV calibration, and the cross-system consistency rules (including that subscription renewals bypass web analytics). Follow it rather than reverse-engineering the previous company's generator.
Keep generated CSVs outside the repo. The Python modules in `synthetic_pitch_data` should read and write in the external `synthetic_data/data/...` tree.
Generate in this order unless the user approves a different dependency model:
   - first generate products using the observed current catalog as the present-day anchor plus a sensible historic and future tail where needed
   - then generate orders as the core commercial timeline
   - then generate customers using the orders output as ground truth where needed
   - only after products, orders, and customers are stable, parallelize dependent raw source datasets such as GA4, Bloomreach, Zendesk, order items, subscription events, or attribution tables
All downstream datasets must reconcile to the same primary and foreign keys, event order, and realistic timestamps unless a selected data issue intentionally introduces a controlled mismatch.

11. Run raw-source post-generation tests.
Run the deterministic validation harness after raw source generation and before any standardization or analytics work. It is a closed loop: it reads the setup yaml thresholds and data-issue checks and reports PASS / FAIL / MANUAL per check, exiting non-zero on any FAIL.

```bash
python3 -m synthetic_pitch_data.validate_raw --company <slug>
```

Treat a non-zero exit as blocking: fix the generator or the targets and regenerate until it passes, rather than rationalizing a FAIL. The harness covers:
   - primary-key uniqueness where uniqueness is expected
   - foreign-key reconciliation across products, orders, customers, order items, and downstream event tables
   - modeling-window and source-specific-window bounds (including reduced windows for large systems)
   - GA4 purchase-event alignment to the commerce order within the documented tolerance (default 30 minutes)
   - metric-trajectory alignment: realized orders, revenue, and AOV versus the documented targets (scaled where operational scaling applies) within the yaml tolerances
   - each selected data issue that declares a registered `check`, against its `expected_prevalence_range`
For the empty-threshold case the harness reports SKIP, not a pass — fill in thresholds so checks actually run. Checks reported MANUAL have no automated signature and must be sense-checked by hand. Record any intentional exceptions caused by selected data issues.

The harness is generic across companies, not per-company. It works off a schema registry (`RAW_SCHEMA` in `synthetic_pitch_data/validate_raw.py`) keyed by canonical source filename and tagged with a logical role, and it validates only the subset of systems a company actually generated. So:
   - A new company that reuses already-known source systems needs no code change — just fill its setup yaml thresholds and data-issue checks.
   - A brand-new source system type needs one `RAW_SCHEMA` entry (filename, role, primary key, foreign keys, and any column hints), which every future company using that system then reuses. Keep it consistent with the matching `references/standard-source-schemas/` doc.
   - A new data-issue check is registered once in `validate_raw.py` and referenced from the setup yaml by name.
   Do not write a separate validation file per company.
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

13. Stage and clean — only after the source phase passes.
This is a gated phase. Do not begin staging until raw generation is complete AND `validate_raw` exits 0 (every check PASS, or a FAIL explicitly recorded under `execution_plan.accepted_waivers`), AND the user has approved moving past the `source_generation` gate. If validation still has un-waived FAILs, fix and regenerate first.
Read `references/stage-cleaning.md` before staging. Then run:

```bash
python3 -m synthetic_pitch_data.staging.run_staging --company <slug>
```

This cleans every produced extract through the shared detector battery and writes cleaned stage tables plus an auto-generated `CLEANING_NOTES.md` under `data/stage/<slug>/`. Key rules:
   - Discover issues from the data by profiling — never from the generators. The staging package is isolated and must not import generator code.
   - Standardize the commerce spine (customers, orders, order_items, products) to the Shopify shape; conform a non-Shopify backend with an adapter first. Clean non-commerce systems (GA4, CRM, support, subscriptions, attribution) within their own standard source schemas.
   - Per-dataset cleaners are reused across all clients on a system, never written per client. A new system needs one dataset spec (or adapter); a new quirk needs one new detector in the shared battery — then refine over time.
   - Review `CLEANING_NOTES.md` and confirm the detected issues are plausible before moving on. Pause for user approval of the `stage_standardization` gate.

14. Generate analytics from the staged tables.
Only after staging is reviewed and approved. Analytics read the cleaned stage tables directly (e.g. retention reads `shopify_orders.csv`). Build the approved analytics outputs, for example:

```bash
RETENTION_AS_OF_DATE=<as_of> python3 -m synthetic_pitch_data.monthly_cohort_retention --company <slug>
```

Retention is computed as of a date and ignores future-dated orders. Validate analytics against the documented trajectory (retention checkpoints, etc.) before delivering.

15. Run a retrospective before considering the engagement done.
Read `references/retrospective.md` and reconcile what actually happened against this skill while the session context is still available: steps skipped, reference docs inferred instead of read, deviations, techniques or modeling rules used that aren't yet in the skill, estimates that drifted from realized, and anything the user had to catch. Apply the clear wins directly (a new reference note, a tightened step, a new `validate_raw` check) and list larger ones as proposals. A finding that produces no change to the skill, a reference doc, or the validator was not really actioned. If nothing meaningful diverged, say so in one line.

## Files to read when needed

- `references/setup-checklist.md`: step-by-step setup and research checklist
- `references/metric-definitions.md`: how every metric is computed (AOV/revenue conventions, promo-inclusive volume, scaling)
- `references/channel-mix-benchmarks.md`: realistic D2C channel mix, unattributed baseline, and attribution-coverage modelling
- `references/seasonality-calendars.md`: non-Gregorian trading peaks (Ramadan/Eid, Lunar New Year, Diwali), why they migrate, and the mix and retention effects they cause
- `references/data-issues-menu.md`: menu of common real-world data issues
- `references/generator-contract.md`: authoring contract for a company `generate_raw.py` — structure, conventions, shared helpers, AOV calibration, cross-system consistency rules
- `references/stage-cleaning.md`: how raw extracts are cleaned/standardized into stage tables, the detector battery, and how to extend it
- `references/standard-source-schemas/index.md`: platform-specific source extract schemas
- `references/standard-stage-schemas/index.md`: canonical stage schemas and mapping guidance
- `references/standard-analytics-schemas/index.md`: canonical analytics schemas derived from stage data
- `references/retrospective.md`: closing reconciliation of the run against this skill, and how to feed gaps back in

## Repo commands

Use these commands from the repo root when useful:

```bash
python3 -m synthetic_pitch_data.validate_raw --company <slug>
python3 -m synthetic_pitch_data.staging.run_staging --company <slug>
python3 -m synthetic_pitch_data.monthly_cohort_retention --company <slug>
```

## Working style

- Prefer browsing current primary sources when facts may have changed.
- Make assumptions explicit and keep them editable.
- Keep the company-specific setup artifact as the single source of truth for generation choices.
- Treat source-system confirmation as evidence-based, not inferential.
- Always stop for plan review and explicit approval before execution.
- Treat products, then orders, then customers as the core source-generation spine unless the user approves a different dependency model.
- Parallelize only after shared ground-truth entities are generated and locked.
- Keep source generation, stage standardization, and analytics generation as separate approval phases. Do not start staging until `validate_raw` passes (or has recorded waivers) and the source phase is approved.
- When cleaning/staging, discover issues by profiling the data, never by consulting the generators. Keep the staging package isolated from generator code.
- Treat the current site catalog and visible promotions as first-class evidence for product and discount modeling.
- Run explicit post-generation tests before considering the dataset complete.
- Do not write generated CSV outputs into the repo.
