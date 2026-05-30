# Google Analytics 4 Reporting API

Use the GA4 Reporting / Data API as the standard GA4 source for purchase and attribution reporting.

Important:

- This standard assumes the Reporting / Data API, not the BigQuery export.
- `defaultChannelGroup` is available in the reporting layer.
- `transactionId` is the documented ecommerce transaction identifier in the Data API.
- The reporting API is not a raw event export. It does not expose raw BigQuery-style fields such as `user_pseudo_id`.
- The reporting API exposes date and time dimensions such as `dateHourMinute`, but not raw microsecond event timestamps.
- If a client uses GA4 BigQuery export, define that as a separate standard source later rather than mixing the two surfaces.

## Orders Reporting Extract

Use this as the standard order-level reporting extract from the GA4 Data API.

`ga4_reporting_orders.csv`

- `date`
- `dateHour`
- `dateHourMinute`
- `transactionId`
- `defaultChannelGroup`
- `sessionDefaultChannelGroup`
- `source`
- `medium`
- `sourceMedium`
- `sourcePlatform`
- `sessionSource`
- `sessionMedium`
- `sessionSourceMedium`
- `sessionSourcePlatform`
- `browser`
- `deviceCategory`
- `platformDeviceCategory`
- `country`
- `region`
- `city`
- `streamId`
- `platform`
- `user_id`
- `itemPromotionId`
- `itemPromotionName`
- `purchaseRevenue`
- `grossPurchaseRevenue`
- `shippingAmount`
- `taxAmount`
- `itemRevenue`
- `grossItemRevenue`
- `transactions`
- `ecommercePurchases`

Notes:

- Use `transactionId` as the foreign key back to commerce orders. Do not invent a separate native `order_id` field for GA4 source data.
- Use `defaultChannelGroup` when you want GA4’s default attributed channel grouping from the reporting layer.
- Use `sessionDefaultChannelGroup` when session-scoped grouping is the better fit.
- `source` and `medium` are key-event scoped reporting dimensions; `sessionSource` and `sessionMedium` are session-scoped.
- `dateHourMinute` is the closest standard timestamp-like field in the reporting API for this use case.
- `user_id` is only available when User-ID is implemented; do not assume it is populated.
- `transactions` and `ecommercePurchases` are metrics, not identifiers, and may need careful query design if you export one row per `transactionId`.

## Order Items Reporting Extract

Use this as the standard item-level reporting extract from the GA4 Data API.

`ga4_reporting_order_items.csv`

- `date`
- `dateHour`
- `dateHourMinute`
- `transactionId`
- `itemId`
- `itemName`
- `itemBrand`
- `itemVariant`
- `itemCategory`
- `itemCategory2`
- `itemCategory3`
- `itemCategory4`
- `itemCategory5`
- `itemListId`
- `itemListName`
- `itemPromotionId`
- `itemPromotionName`
- `itemRevenue`
- `grossItemRevenue`
- `itemRefundAmount`
- `itemDiscountAmount`
- `itemsPurchased`
- `itemPurchaseQuantity`

Notes:

- Use `transactionId` as the foreign key back to `ga4_reporting_orders.csv`.
- This is a reporting extract, not a raw flattened export of the underlying event payload.
