"""Stage cleaner for Shopify customers. Reusable across all Shopify clients."""

from __future__ import annotations

from ..cleaning_common import DatasetSpec

SPEC = DatasetSpec(
    name="shopify_customers.csv",
    role="customers",
    source_files=["shopify_customers.csv"],
    key="id",
    required=["id", "created_at"],
    timestamp_cols=["created_at", "updated_at"],
    email_cols=["email"],
    country_cols=["default_address_country_code"],
    upper_cols=["currency"],
    lower_enum_cols=["state"],
    test_pattern_cols=["email", "first_name", "last_name", "tags"],
    provides_keys=["id"],
    static_notes=[
        "Prospects/leads with a valid creation timestamp are retained even with no orders.",
    ],
)
