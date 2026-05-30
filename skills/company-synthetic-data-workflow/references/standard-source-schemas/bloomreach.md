# Bloomreach Engagement

Use Bloomreach event exports for campaign-performance source data.

Important:

- The official docs support exporting a specific event type, and exported event data is not modified by Bloomreach.
- Email and SMS campaign performance live in the `campaign` event stream rather than in separate native `sends`, `opens`, and `clicks` tables.
- SMS clicks require the Campaign Link Shortener for `clicked` status tracking.
- `opened` is documented for email, not SMS.

## Campaign Events

Use a single raw campaign-event export as the standard source shape for email and SMS campaign performance.

`bloomreach_campaign_events.csv`

- `timestamp`
- `status`
- `campaign_name`
- `campaign_id`
- `action_type`
- `action_name`
- `action_id`
- `integration_id`
- `integration_name`
- `integration_type`
- `campaign_policy`
- `consent_category`
- `subject`
- `language`
- `recipient`
- `sent_timestamp`
- `message`
- `message_id`
- `comment`
- `error`
- `code`
- `cumulative`
- `ip`
- `user-agent`
- `url`
- `city`
- `country`
- `number_of_message_parts`
- `sender`
- `status_code`
- `preset_channel`
- `platform`

Notes:

- Filter to the `campaign` event type in Bloomreach exports.
- Use `action_type` to separate email and sms within the same export.
- Model sends, opens, clicks, deliveries, bounces, and failures from the `status` field rather than expecting separate native files.
- Documented statuses include `enqueued`, `enqueue_failed`, `suppressed`, `delivered`, `opened`, `clicked`, `soft_bounced`, `hard_bounced`, `preblocked`, `complained`, `unsubscribed`, `sent`, `failed`, `incoming_message`, `rejected`, `success`, `aborted`, and `read`, but status availability varies by channel and provider.
- Bloomreach data exports always place the event `timestamp` as the last column.
