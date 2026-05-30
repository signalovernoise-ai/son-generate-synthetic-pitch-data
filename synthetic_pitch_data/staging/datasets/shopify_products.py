"""Stage cleaner for the Shopify products catalog. Reusable across all Shopify clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="shopify_products.csv",
    role="products",
    source_files=["shopify_products.csv"],
    key="variant_id",
    required=["product_id", "variant_id"],
    timestamp_cols=["published_at", "created_at", "updated_at"],
    lower_enum_cols=["status", "product_type"],
    provides_keys=["product_id", "variant_id", "sku"],
)
