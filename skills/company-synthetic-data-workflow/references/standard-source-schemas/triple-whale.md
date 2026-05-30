# Triple Whale

Use the Customer Journey Attribution endpoint specified below as the raw source:

- `POST https://api.triplewhale.com/api/v2/attribution/get-orders-with-journeys-v2`

Important:

- The endpoint is officially documented and supports `shop`, `startDate`, `endDate`, `page`, `pageSize`, and `excludeJourneyData`.
- The public endpoint reference confirms that the response contains orders, attribution data, and optionally journey events, but it does not enumerate the full response object field-by-field.
- Because the wire-format fields are not fully published, preserve the raw payload and then extract source tables using official Triple Whale ontology field names.

## Raw Attribution Payload

Use this as the raw landing format for the endpoint response.

`triplewhale_customer_journey_attribution_raw.jsonl`

Notes:

- Preserve the response object exactly as returned by the API.
- Use one JSON object per order or response row, depending on the response pagination payload.
- Keep `excludeJourneyData = false` when journey-step detail is required.

## Attributed Orders

Use this as the extracted order-level source shape from the raw endpoint payload, aligned to official Triple Whale attribution and order ontology fields.

`triplewhale_customer_journey_attribution_orders.csv`

- `shop_id`
- `shop_name`
- `order_id`
- `order_name`
- `created_at`
- `currency`
- `customer_id`
- `customer_email`
- `session_id`
- `triple_id`
- `channel`
- `campaign_id`
- `campaign_name`
- `ad_id`
- `adset_id`
- `source_name`
- `utm_source`
- `utm_medium`
- `click_ts`
- `model`
- `is_new_customer`

Notes:

- These field names align to the official Pixel Orders and related Triple Whale ontology docs.
- Triple Whale documents Pixel Orders as one row per order per attributed ad or channel under multi-touch models, so a single order can appear multiple times.
- Treat this as an extracted source table from the endpoint payload, not as a guarantee that the raw API response is already flat in this shape.

## Journey Events

Use this as the extracted event-level source shape when journey data is included in the endpoint response.

`triplewhale_customer_journey_events.csv`

- `order_id`
- `session_id`
- `triple_id`
- `customer_id`
- `email`
- `event_time`
- `type`
- `event_name`
- `source`
- `referrer`
- `url`
- `query_params`
- `page_type`
- `product_id`
- `product_name`
- `device`
- `lead_click_ts`
- `is_new_customer`
- `subscription_id`

Notes:

- These field names align to the official Customer Journey ontology docs.
- Keep journey events separate from attributed orders because the docs model the journey table as one row per event.
