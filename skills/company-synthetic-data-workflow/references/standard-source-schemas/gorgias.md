# Gorgias

Use Gorgias as the standard support source for ecommerce brands running the Gorgias helpdesk. It
plays the same role in the dataset as Zendesk (`zendesk.md`) — pick one helpdesk per company.

Detection: `config.gorgias.chat` bundle loader in the storefront, a `*.gorgias.help` public help
centre, or the Gorgias app in the store's installed-app list. The chat bundle URL usually carries
the Shopify store handle (`?shop=<handle>.myshopify.com`), which doubles as commerce confirmation.

Important:

- Gorgias is ecommerce-native: tickets can carry the linked Shopify **customer** and **order**, which
  Zendesk does not do natively. That linkage is **agent- or rule-applied, not guaranteed** — a large
  share of tickets have no order id, and chat/social tickets often arrive from an address that
  matches no customer record. Model it as sparse, and never as an orphan reference.
- A ticket is a conversation, not a message. Message-level detail is a separate extract; do not
  flatten messages into the ticket row.
- `channel` (where the conversation happened) and `via` (how it entered) are distinct fields and
  routinely disagree; keep both source-shaped.
- Satisfaction is a 1-5 integer, not Zendesk's good/bad enum. Do not map one onto the other in the
  raw layer.

## Tickets

`gorgias_tickets.csv`

- `id`
- `created_datetime`
- `updated_datetime`
- `opened_datetime`
- `closed_datetime`
- `status`
- `priority`
- `channel`
- `via`
- `subject`
- `excerpt`
- `from_email`
- `customer_id`
- `shopify_customer_id`
- `shopify_order_id`
- `assignee_user_id`
- `team_id`
- `tags`
- `satisfaction_score`
- `messages_count`
- `is_spam`
- `trashed_datetime`
- `language`

Notes:

- `id` is the Gorgias ticket id and is the primary key.
- `customer_id` is Gorgias's own contact id; `shopify_customer_id` and `shopify_order_id` are the
  commerce foreign keys and are **sparse by design**. Where populated they must reference real
  rows.
- `status` is `open` / `closed`. `closed_datetime` is blank while open.
- `channel` is `email` / `chat` / `sms` / `phone` / `facebook` / `instagram` / `contact-form`;
  `via` is the ingestion path (`email`, `chat`, `api`, `help-center`, …).
- `satisfaction_score` is 1-5 and is populated on only a minority of closed tickets.
- `tags` is a comma-separated list; support taxonomies drift over time, so expect casing and
  naming inconsistency across the history.

## Standardised stage view

The stage cleaner conforms this to the shared `support_tickets` role alongside the Zendesk spec:
canonical `ticket_id`, `created_at`, `updated_at`, `status`, `priority`, `channel`, `requester_email`,
`order_id`, `customer_id`, `tags`, `satisfaction`. Native fields are retained alongside the
canonical ones.
