# Ordergroove

Use Ordergroove subscription and order APIs plus webhook events for subscription-commerce source data.

Important:

- Ordergroove officially supports subscriptions, orders, and webhook events.
- The REST API overview states that Ordergroove manages subscription commerce data for customers, subscriptions, items, and orders.
- The GraphQL `orders` query supports filtering by `subscription` public ID, which validates the existence of subscription-order extraction.
- Webhook docs list subscriber, subscription, order, and order item event families.

## Subscriptions

Use this as the standard subscription source shape.

`ordergroove_subscriptions.csv`

- `publicId`
- `externalId`
- `subscriptionType`
- `live`
- `quantity`
- `price`
- `currencyCode`
- `frequencyDays`
- `every`
- `everyPeriod`
- `startDate`
- `cancelled`
- `cancelReason`
- `cancelReasonCode`
- `sessionId`
- `merchantOrderId`
- `offerPublicId`
- `created`
- `updated`
- `extraData`
- `reminderDays`

Notes:

- These fields are validated against Ordergroove’s documented `SubscriptionType` and object-reference docs.
- `everyPeriod` is documented as `1 = Days`, `2 = Weeks`, `3 = Months` in the object-reference docs; keep the raw enum and document any readable mapping separately.
- If bundle subscriptions are in scope, preserve `components` as a nested or exploded companion extract.

## Subscription Orders

Use this as the standard order-level source shape for Ordergroove orders tied to subscriptions.

`ordergroove_subscription_orders.csv`

- `publicId`
- `status`
- `subTotal`
- `taxTotal`
- `shippingTotal`
- `discountTotal`
- `total`
- `place`
- `created`
- `updated`
- `cancelled`
- `orderMerchantId`
- `rejectedMessage`
- `extraData`
- `locked`
- `oosFreeShipping`
- `currencyCode`
- `tries`
- `genericErrorCount`
- `merchantPublicId`
- `hasPlan`

Notes:

- These fields are validated against Ordergroove’s documented `OrderType`.
- The GraphQL `orders` query supports filtering by `subscription` public ID, so this table should be extracted either by filtering to a subscription or by flattening order items with subscription references.
- If you need item-level subscription linkage, flatten `items.nodes` separately because the documented `ItemType` contains `subscription`, `orderPublicId`, `publicId`, `quantity`, `price`, and `totalPrice`.

## Events

Use webhook events as the standard event source. Because payloads vary by event family, keep the raw webhook payload as JSONL.

`ordergroove_events.jsonl`

Common event envelope:

- `id`
- `type`
- `created`
- `data.object.type`
- `data.object.merchant`
- `data.object.public_id`

Supported event families validated in the docs:

- Subscriber events: `subscriber.create`, `subscriber.cancel`
- Subscription events: `subscription.create`, `subscription.cancel`, `subscription.sku_swap`, `subscription.reactivate`, `subscription.change_frequency`, `subscription.change_components`, `subscription.change_quantity`, `subscription.change_shipping_address`, `subscription.change_payment`, `subscription.change_live`
- Order events: `order.change_shipping_address`, `order.change_payment`, `order.change_billing`, `order.change_next_order_date`, `order.skip_order`, `order.send_now`, `order.cancel`, `order.success`, `order.generic_error`, `order.reject`, `order.reminder`, `order.retryable_placement_failure`
- Order item events: `item.create`, `item.change_quantity`, `item.remove`, `item.item_subscribe`, `item.update_price`, `item.successfully_placed`

Notes:

- Preserve raw event payloads because the exact `data` object varies by event type.
- Verify webhook signatures using the documented `OrderGroove-Signature` header and HMAC-SHA256 scheme before ingestion.
