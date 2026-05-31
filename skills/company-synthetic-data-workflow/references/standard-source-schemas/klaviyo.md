# Klaviyo

Use Klaviyo event exports for email and SMS campaign-performance source data. Klaviyo
is the dominant email/SMS CRM+CDP in DTC ecommerce (roughly two-thirds of the
ecommerce-marketing category), so it is the default campaign source for Shopify-centric
brands. It plays the same role in the dataset as Bloomreach (`bloomreach.md`) does for
brands on that platform — pick one campaign system per company, not both, unless evidence
shows a genuine migration.

Important:

- Klaviyo is **event/metric-per-row**, not status-per-row. Each engagement is its own
  event whose `metric_name` names the action (`Opened Email`, `Clicked SMS`, …). This is
  the key shape difference from Bloomreach, which carries one row per recipient with a
  `status` field. Do **not** invent a single `status` column for Klaviyo.
- The Events API returns events with a flat set of top-level attributes plus nested
  `event_properties`. Klaviyo uses `$`-prefixed property names (`$message`, `$flow`,
  `$value`, `$attributed_message`, `$attributed_channel`); keep them verbatim — exported
  event data is not renamed.
- **SMS has no open tracking.** There is no `Opened SMS` metric — delivery, clicks, and
  consent are the only SMS engagement signals. Email has opens.
- Klaviyo metrics are channel-specific. Use `metric_name` (and the `channel` send
  channel) to separate email and SMS within the same export.
- Conversions (`Placed Order`) carry attribution back to the campaign or flow that drove
  them via `$attributed_message` / `$attributed_flow` / `$attributed_channel`, and a
  revenue figure in `$value`. The link to the commerce order is soft (profile `email` +
  `$value` + timestamp), not a guaranteed foreign key — real Klaviyo exports do not
  reliably carry the Shopify order id, so do not enforce a hard order FK.

## Campaign & flow events

Use a single raw event export as the standard source shape for email and SMS performance.

`klaviyo_events.csv`

- `event_id`
- `timestamp`
- `metric_id`
- `metric_name`
- `profile_id`
- `email`
- `phone_number`
- `channel`
- `$message`
- `campaign_id`
- `campaign_name`
- `$flow`
- `$flow_message_id`
- `flow_name`
- `subject`
- `$variation`
- `url`
- `bounce_type`
- `client_name`
- `client_type`
- `num_segments`
- `$attributed_message`
- `$attributed_flow`
- `$attributed_channel`
- `$value`

Notes:

- `event_id` is unique per event (Klaviyo UUID) — it is the primary key.
- `timestamp` is an ISO-8601 datetime in the account timezone (UTC for synthetic data).
- A campaign send populates `campaign_id` / `campaign_name` / `$message`; a flow send
  populates `$flow` / `$flow_message_id` / `flow_name` / `$message`. Exactly one of the
  two paths is set per messaging event.
- `subject` is email-only (blank for SMS). `num_segments` is SMS-only (message parts).
  `client_name` / `client_type` populate on email open/click events.
- `bounce_type` is `hard` or `soft` on `Bounced Email`; blank otherwise.
- `$value` and the `$attributed_*` fields populate only on `Placed Order` conversion
  events.

### Documented native metrics

Email: `Received Email`, `Opened Email`, `Clicked Email`, `Bounced Email`,
`Marked Email as Spam`, `Unsubscribed`, `Dropped Email`.

SMS: `Received SMS`, `Sent SMS`, `Clicked SMS`, `Failed to Deliver SMS`,
`Unsubscribed from SMS`, `Consented to Receive SMS`.

Conversion: `Placed Order` (attributed to the driving message/flow).

Metric availability varies by channel and account configuration; not every metric appears
for every send (e.g. no opens for SMS, `Marked Email as Spam` is rare).
