# Setup Checklist

Use this checklist when preparing a company-specific synthetic dataset.

## 1. Company brief

- Company name
- Website
- Time window: default 18 months historic plus 6 months future, unless explicitly overridden
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
- Public interviews, investor updates, or press releases
- Job descriptions mentioning systems or data tools
- App-store, partner, or vendor directory evidence
- Category seasonality and promotional windows
- Retail presence versus pure D2C

Capture exact current product names and prices from the live site where possible. Use those directly in the products dataset.
If you introduce delisted or historic products, keep them close to the observed current assortment and price architecture.

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
- current catalog, pricing, and promotion evidence
- confirmed systems and supporting evidence
- source schemas to use
- stage tables to build
- analytics tables to build
- selected data issues
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

## 7. Output design

- Raw source-shaped extracts by system
- Platform-specific standard tables by system, for example Shopify orders and customers or Zendesk tickets
- Standardized stage tables
- Standardized analytics tables required for the pitch
- Product tables grounded in the observed current catalog, with sensible historic or delisted extensions where needed
- Notes on what the AI system should detect and recommend

## 8. Generation sequencing

- Generate orders first as the commercial ground truth
- Generate customers second, anchored to the order population and identity rules
- Generate products third, grounded in the observed current catalog and pricing
- Generate dependent system extracts only after orders, customers, and products are stable
- Parallelize only across downstream datasets that share the same keys and timeline assumptions
- Validate timestamp realism across systems before delivery
- Keep all generated records inside the approved modeling window

## 9. Post-generation validation

- Check primary-key uniqueness in each controlled output
- Check foreign-key reconciliation across orders, customers, products, order items, and downstream datasets
- Check timestamp ordering within each system and across linked systems
- For GA4 and commerce joins, require purchase timestamps to be within 30 minutes of the corresponding commerce order unless a different tolerance is explicitly approved
- Check that promotion and discount fields are consistent with the modeled catalog and offer strategy
- Check that all records fall within the approved historic and future date window
- Record any intentional validation failures that are present because of selected data issues
