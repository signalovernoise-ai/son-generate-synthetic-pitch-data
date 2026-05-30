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
- Category seasonality and promotional windows
- Retail presence versus pure D2C

Capture exact current product names and prices from the live site where possible. Use those directly in the products dataset.
If you introduce delisted or historic products, keep them close to the observed current assortment and price architecture.
Use any credible revenue, growth, or operating metrics you find here to shape the pre-generation trend assumptions.
Capture delivery-threshold logic explicitly because it affects AOV, item count per order, and discount behavior.

## 3. Commercial modeling assumptions

- Revenue band
- Monthly order volume band
- AOV range
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

## 4. Source-system inventory

For each source system capture:

- System name
- Confirmation source: public evidence, user-confirmed, or call-note confirmed
- Evidence link or note
- Data domain: commerce, CRM, lifecycle, support, ads, web analytics, finance, warehouse
- Export shape: standard connector schema, vendor export, custom tables
- Platform resource scope: orders, customers, order items, products, tickets, events, campaigns, etc.
- Join keys available
- Known limitations
- Whether the schema is based on a real sample extract, official documentation, or client-provided schema notes

If a system cannot be confirmed, do not include it in generation. Record it as an open question instead.

## 5. Plan and approval checkpoint

Before any generation work begins, present a plan for user approval that covers:

- company brief and scope
- modeling window and any override to the default 18 historic months plus 6 future months
- any reduced time windows for large source systems and why they are acceptable
- current catalog, pricing, and promotion evidence
- delivery-pricing evidence and free-delivery threshold assumptions
- proposed growth, seasonality, AOV, retention, refund, and mix trajectories before generation
- confirmed systems and supporting evidence
- source schemas to use
- raw source outputs to build now
- stage tables to build later
- analytics tables to build later
- proposed data-issue mix, severity, and expected prevalence
- post-generation validation tests and thresholds
- generation sequence and any parallelizable groups
- open questions and assumptions

Do not execute generation until the user approves or refines the plan.

## 6. Data-issue selection

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

## 7. Output design

- Raw source-shaped extracts by system
- Platform-specific standard tables by system, for example Shopify orders and customers or Zendesk tickets
- Standardized stage tables, only after raw-source review and approval
- Standardized analytics tables required for the pitch, only after source and stage approval
- Product tables grounded in the observed current catalog, with sensible historic or delisted extensions where needed
- Notes on what the AI system should detect and recommend

## 8. Generation sequencing

- Generate products first, grounded in the observed current catalog and pricing
- Generate orders second as the commercial ground truth
- Generate customers third, anchored to the order population and identity rules
- Generate dependent raw source system extracts only after products, orders, and customers are stable
- Parallelize only across downstream datasets that share the same keys and timeline assumptions
- Validate timestamp realism across systems before delivery
- Keep all generated records inside the approved modeling window
- For large datasets such as CRM, support, or event streams, consider a shorter approved source window anchored to the core products, orders, and users records

## 9. Phase gates

- Do not generate stage outputs until raw source datasets have been generated, validated, and accepted by the user
- Do not generate analytics outputs until stage outputs have been generated, validated, and accepted by the user
- Treat source, stage, and analytics as separate review checkpoints

## 10. Post-generation validation

- Check primary-key uniqueness in each controlled output
- Check foreign-key reconciliation across orders, customers, products, order items, and downstream datasets
- Check timestamp ordering within each system and across linked systems
- For GA4 and commerce joins, require purchase timestamps to be within 30 minutes of the corresponding commerce order unless a different tolerance is explicitly approved
- Check that promotion and discount fields are consistent with the modeled catalog and offer strategy
- Check that all records fall within the approved historic and future date window
- Check that any reduced windows for large source systems are actually respected
- Check that revenue, order volume, AOV, refund rate, and repeat behavior follow the approved pre-generation trajectories
- Record any intentional validation failures that are present because of selected data issues
