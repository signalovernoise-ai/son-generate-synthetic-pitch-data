from __future__ import annotations

import pandas as pd

from synthetic_pitch_data.cleaning_common import (
    SOURCE_ROOT,
    clean_string,
    format_utc,
    normalize_country,
    print_summary,
    test_pattern_mask,
    to_utc,
    write_stage_csv,
)


BUSINESS = "Shopify_2"
SOURCE_FILE = SOURCE_ROOT / BUSINESS / "shopify_customers_drinks.csv"


def build_users() -> pd.DataFrame:
    raw = pd.read_csv(SOURCE_FILE, dtype={"customer_id": "string"})

    user_id = clean_string(raw["customer_id"])
    created_at = to_utc(raw["Created at"])

    valid = user_id.notna() & created_at.notna()
    valid &= ~test_pattern_mask(raw, ["Email", "First Name", "Last Name", "Tags"])

    users = pd.DataFrame(
        {
            "user_id": user_id,
            "created_at": format_utc(created_at),
            "country": normalize_country(raw["Country"]),
        }
    )
    return users[valid].drop_duplicates("user_id", keep="first").reset_index(drop=True)


def main() -> None:
    raw_rows = len(pd.read_csv(SOURCE_FILE, usecols=["customer_id"]))
    staged = build_users()
    output_path = write_stage_csv(staged, BUSINESS, "users.csv")
    print_summary("Shopify_2 users", raw_rows, len(staged), output_path)


if __name__ == "__main__":
    main()
