"""Registry of stage dataset specs in dependency order, plus backend detection.

Dependency order matters: parents (products, customers, orders) must be staged
before children so foreign-key checks can resolve against the *cleaned* parent.
"""

from __future__ import annotations

from .datasets import (
    bloomreach_campaign_events,
    ga4_purchase_events,
    ga4_purchase_items,
    google_ads_campaign_performance,
    gorgias_tickets,
    klaviyo_events,
    meta_ad_creatives,
    meta_ads_insights,
    ordergroove_events,
    ordergroove_subscription_orders,
    ordergroove_subscriptions,
    recharge_subscription_orders,
    recharge_subscriptions,
    shopify_customers,
    shopify_order_items,
    shopify_orders,
    shopify_products,
    triplewhale_attributed_orders,
    triplewhale_journey_events,
    zendesk_tickets,
)

# Dependency-ordered list of all known stage dataset specs.
STAGE_SPECS = [
    shopify_products.SPEC,
    shopify_customers.SPEC,
    shopify_orders.SPEC,
    shopify_order_items.SPEC,
    ga4_purchase_events.SPEC,
    ga4_purchase_items.SPEC,
    triplewhale_attributed_orders.SPEC,
    triplewhale_journey_events.SPEC,
    ordergroove_subscriptions.SPEC,
    ordergroove_subscription_orders.SPEC,
    ordergroove_events.SPEC,
    # Recharge: subscriptions before charges, so the charge FK resolves against the
    # cleaned parent. A company runs one subscription platform, never both.
    recharge_subscriptions.SPEC,
    recharge_subscription_orders.SPEC,
    bloomreach_campaign_events.SPEC,
    klaviyo_events.SPEC,
    google_ads_campaign_performance.SPEC,
    meta_ads_insights.SPEC,
    meta_ad_creatives.SPEC,
    zendesk_tickets.SPEC,
    gorgias_tickets.SPEC,
]
