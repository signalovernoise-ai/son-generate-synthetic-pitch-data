"""Adapter: conform a custom Postgres commerce backend to the Shopify source shape.

A custom backend (user.csv / fact_order.csv) is reshaped into Shopify-named frames
(shopify_customers.csv / shopify_orders.csv) BEFORE cleaning, so the standard Shopify
per-dataset cleaners then apply unchanged. This is how "standardise to the Shopify
backend" is realised for non-standard sources.

The adapter only renames/remaps schema. It does not clean — the detector battery does.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

USER_FILES = ["user.csv"]
ORDER_FILES = ["fact_order.csv", "fact_order (1).csv"]

# Source status -> Shopify financial_status. Non-final values (cancelled, pending,
# failed) are mapped through and then dropped by the standard status filter.
STATUS_MAP = {
    "completed": "paid",
    "complete": "paid",
    "paid": "paid",
    "refunded": "refunded",
    "partially_refunded": "partially_refunded",
    "partial_refund": "partially_refunded",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "pending": "pending",
    "failed": "failed",
}

CUSTOMER_MAP = {
    "user_id": "id",
    "email": "email",
    "first_name": "first_name",
    "last_name": "last_name",
    "phone": "phone",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "marketing_opt_in": "accepts_marketing",
    "city": "default_address_city",
    "postcode": "default_address_zip",
    "country": "default_address_country_code",
    "source": "tags",
}

ORDER_MAP = {
    "order_id": "id",
    "user_id": "customer_id",
    "order_number": "order_number",
    "created_at": "created_at",
    "processed_at": "processed_at",
    "currency": "currency",
    "subtotal": "subtotal_price",
    "discount_total": "total_discounts",
    "tax_total": "total_tax",
    "shipping_total": "total_shipping_price_set_amount",
    "total": "total_price",
    "item_count": "line_items_count",
    "channel": "source_name",
    "ip_country": "billing_address_country_code",
}


def _first_present(src: Path, names: list[str]) -> Path | None:
    for n in names:
        if (src / n).exists():
            return src / n
    return None


def detect(src: Path) -> bool:
    """True if this looks like a custom Postgres commerce backend (no Shopify files)."""
    has_shopify = (src / "shopify_orders.csv").exists() or (src / "shopify_customers.csv").exists()
    has_pg = _first_present(src, ORDER_FILES) is not None or _first_present(src, USER_FILES) is not None
    return has_pg and not has_shopify


def adapt(src: Path) -> dict[str, pd.DataFrame]:
    """Return Shopify-shaped frames keyed by canonical Shopify filename."""
    out: dict[str, pd.DataFrame] = {}
    user_path = _first_present(src, USER_FILES)
    if user_path is not None:
        u = pd.read_csv(user_path, dtype=str, keep_default_na=False)
        out["shopify_customers.csv"] = u.rename(columns={k: v for k, v in CUSTOMER_MAP.items() if k in u.columns})

    order_path = _first_present(src, ORDER_FILES)
    if order_path is not None:
        o = pd.read_csv(order_path, dtype=str, keep_default_na=False)
        o = o.rename(columns={k: v for k, v in ORDER_MAP.items() if k in o.columns})
        if "financial_status" not in o.columns and "status" in o.columns:
            o["financial_status"] = o["status"].astype("string").str.strip().str.lower().map(STATUS_MAP).fillna(
                o["status"].astype("string").str.strip().str.lower()
            )
        out["shopify_orders.csv"] = o
    return out
