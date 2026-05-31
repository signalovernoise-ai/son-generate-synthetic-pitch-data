# Setup Checklist

Use this checklist when preparing a company-specific synthetic dataset.

## 1. Company brief

- Company name
- Website
- Time window: default 18 months historic plus 6 months future, unless explicitly overridden
- Source-specific window reductions for large datasets where needed, for example CRM, support, or event streams
- Country or primary markets
- Currency
- Category and subcategory
- Core products and hero SKUs
- Purchase cadence: one-off, replenishment, subscription, mixed
- Audience and price positioning

## 2. Research pass

Browse the web for current signals and capture the source links:

- Product catalog and price points
- Bundles, subscriptions, or memberships
- Visible discounts, welcome offers, bundles, and promotional banners
- Delivery pricing, including free-delivery thresholds or blanket free-shipping policies
- Public interviews, investor updates, or press releases
- Company filings and credible reporting on revenue, growth, customer trends, or market expansion
- Job descriptions mentioning systems or data tools
- App-store, partner, or vendor directory evidence
- Website technology-profiler scan (BuiltWith / Wappalyzer / on-site script tags, DNS and email headers) — run this as a standard step for every client to detect the real martech, analytics, subscription, and CRM/ESP stack, particularly the email/SMS campaign system
- Category seasonality and promotional windows
- Retail presence versus pure D2C

Capture exact current product names and prices from the live site where possible. Use those directly in the products dataset.
If you introduce delisted or historic products, keep them close to the observed current assortment and price architecture.
Use any credible revenue, growth, or operating metrics you find here to shape the pre-generation trend assumptions.
Capture delivery-threshold logic explicitly because it affects AOV, item count per order, and discount behavior.

## 3. Commercial modeling assumptions

- Assumed annual revenue level
- Assumed annual revenue growth rates
- Monthly order volume level
- AOV level
- AOV shape, including tail behavior and whether large-order segments exist
- Gross refund rate
- Customer growth trend
- New versus repeat order mix
- Country mix
- Subscription share if relevant
- Whether retention changes are driven by true behavior changes, customer-mix shifts, or both
- Any major product or subscription launch that changes seasonality or repeat patterns

Before generation, turn these into an explicit time-series proposal:

- monthly revenue trend over the approved window
- monthly order-volume trend over the approved window
- AOV trajectory over time
- repeat-rate or retention trajectory over time
- refund-rate trajectory over time
- seasonality peaks and troughs by month or campaign window
- metric inflection points caused by launches, promotions, migrations, or category shifts

Quantify these wherever possible:

- annual revenue assumptions by year or run-rate
- annual or period-on-period growth rates
- baseline retention levels such as M1, M3, M6, and M12 where relevant
- baseline new vs repeat mix
- baseline refund rate
- expected uplift or drag from promotions, launches, seasonality, or migration events

## 4. Volume estimate

Before generation, estimate likely row counts for:

- products
- orders
- customers
- order items
- CRM / lifecycle events
- attribution events
- support tickets

If projected total raw rows look too large to generate and review comfortably, use this escalation order:

- first propose reducing the historic window from 18 months to 12 months
- then propose scaling down operational row counts while preserving the approved business metrics and time-series behavior

Do not shrink low-row-count dimension tables such as products or other small reference tables unless the user explicitly asks for it. Apply scaling mainly to high-volume fact and event tables.

Record the estimated row counts and the reason for any proposed reduction in the approval plan.

## 5. Source-system inventory

For each source system capture:

- System name
- Confirmation source: technology-profiler detection, public evidence, user-confirmed, or call-note confirmed
- Evidence link or note (include the technology-profiler result, and note any conflict between it and call notes / user belief for the user to resolve)
- Data domain: commerce, CRM, lifecycle, support, ads, web analytics, finance, warehouse
- Export shape: standard connector schema, vendor export, custom tables
- Platform resource scope: orders, customers, order items, products, tickets, events, campaigns, etc.
- Join keys available
- Known limitations
- Whether the schema is based on a real sample extract, official documentation, or client-provided schema notes

If a system cannot be confirmed, do not include it in generation. Record it as an open question instead.

## 6. Plan and approval checkpoint

Before any generation work begins, present a plan for user approval that covers:

- company brief and scope
- modeling window and any override to the default 18 historic months plus 6 future months
- any reduced time windows for large source systems and why they are acceptable
- current catalog, pricing, and promotion evidence
- delivery-pricing evidence and free-delivery threshold assumptions
- proposed quantified growth, seasonality, AOV, retention, refund, and mix trajectories before generation, shown in the approval message as an explicit month-by-month table (revenue, orders, AOV, and the seasonality multiplier or note per month) — not only in the setup artifact. State whether seasonality is a separate multiplier layer or baked into the monthly volume path, and do not record multipliers the generator will not apply
- explicit annual revenue assumptions, annual growth rates, and the expected effect of promos or seasonality on key metrics
- confirmed systems and supporting evidence
- source schemas to use
- raw source outputs to build now
- stage tables to build later
- analytics tables to build later
- estimated raw row counts by dataset
- any proposed volume controls, including a cut to 12 historic months or operational row-count scaling
- which low-row-count dimensions are protected from scaling
- proposed data-issue mix, severity, and expected prevalence
- post-generation validation tests and thresholds
- generation sequence and any parallelizable groups
- open questions and assumptions

Do not execute generation until the user approves or refines the plan.

## 7. Data-issue selection

Use the issue menu to choose realistic imperfections:

- identity fragmentation
- time-zone drift
- duplicate customers or orders
- refunds inconsistently represented
- partial refunds without amounts
- delayed attribution syncs
- missing country or channel fields
- test or internal traffic leakage
- schema drift over time
- migrated IDs or mixed identifier formats
- staging contamination or duplicate-like operational rows

For each selected issue, define:

- severity
- expected prevalence or approximate row count
- affected systems
- visibility to the downstream analyst
- rationale for why it fits the company and time period

## 8. Output design

- Raw source-shaped extracts by system
- Platform-specific standard tables by system, for example Shopify orders and customers or Zendesk tickets
- Standardized stage tables, only after raw-source review and approval
- Standardized analytics tables required for the pitch, only after source and stage approval
- Product tables grounded in the observed current catalog, with sensible historic or delisted extensions where needed
- Notes on what the AI system should detect and recommend

## 9. Generation sequencing

- Generate products first, grounded in the observed current catalog and pricing
- Generate orders second as the commercial ground truth
- Generate customers third, anchored to the order population and identity rules
- Generate dependent raw source system extracts only after products, orders, and customers are stable
- Parallelize only across downstream datasets that share the same keys and timeline assumptions
- Validate timestamp realism across systems before delivery
- Keep all generated records inside the approved modeling window
- For large datasets such as CRM, support, or event streams, consider a shorter approved source window anchored to the core products, orders, and users records

## 10. Phase gates

- Do not generate stage outputs until raw source datasets have been generated, validated, and accepted by the user
- Do not generate analytics outputs until stage outputs have been generated, validated, and accepted by the user
- Treat source, stage, and analytics as separate review checkpoints

## 11. Post-generation validation

- Check primary-key uniqueness in each controlled output
- Check foreign-key reconciliation across orders, customers, products, order items, and downstream datasets
- Check timestamp ordering within each system and across linked systems
- For GA4 and commerce joins, require purchase timestamps to be within 30 minutes of the corresponding commerce order unless a different tolerance is explicitly approved
- Check that promotion and discount fields are consistent with the modeled catalog and offer strategy
- Check that all records fall within the approved historic and future date window
- Check that any reduced windows for large source systems are actually respected
- Check that any approved row-volume scaling has been applied consistently
- Check that revenue, order volume, AOV, refund rate, and repeat behavior follow the approved quantified pre-generation trajectories
- Record any intentional validation failures that are present because of selected data issues
