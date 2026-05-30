# Zendesk

Use Zendesk-aligned source schemas when the company uses Zendesk for support.

## Tickets

Use this as the default expected Zendesk ticket shape.

`zendesk_tickets.csv`

- `id`
- `created_at`
- `updated_at`
- `status`
- `priority`
- `type`
- `subject`
- `description`
- `requester_id`
- `submitter_id`
- `assignee_id`
- `organization_id`
- `group_id`
- `via_channel`
- `ticket_form_id`
- `brand_id`
- `recipient`
- `tags`
- `satisfaction_score`

Notes:

- If available, also capture ticket-to-order or ticket-to-customer linkage fields.
- Free-text return reasons or support categories should remain source-shaped unless a mapping is explicitly defined.
