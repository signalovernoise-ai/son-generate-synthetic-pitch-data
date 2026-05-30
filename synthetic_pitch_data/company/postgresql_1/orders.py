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


BUSINESS = "PostgreSQL_1"
ORDERS_FILE = SOURCE_ROOT / BUSINESS / "fact_order (1).csv"
USERS_FILE = SOURCE_ROOT / BUSINESS / "user.csv"


def cleaned_users() -> pd.DataFrame:
    raw_users = pd.read_csv(USERS_FILE, dtype={"user_id": "string"})
    user_id = clean_string(raw_users["user_id"])
    created_at = to_utc(raw_users["created_at"])

    valid = user_id.notna() & created_at.notna()
    valid &= ~test_pattern_mask(raw_users, ["email", "first_name", "last_name", "source"])

    users = pd.DataFrame({"user_id": user_id, "country": normalize_country(raw_users["country"])})
    return users[valid].drop_duplicates("user_id", keep="first")


def near_duplicate_mask(raw_orders: pd.DataFrame, active_mask: pd.Series) -> pd.Series:
    candidates = raw_orders[active_mask].copy()
    candidates["_ordered_at"] = to_utc(candidates["created_at"])
    candidates["_total"] = pd.to_numeric(candidates["total"], errors="coerce").round(2)
    candidates["_order_id_num"] = pd.to_numeric(candidates["order_id"], errors="coerce")

    candidates = candidates.sort_values(["user_id", "_total", "_ordered_at", "_order_id_num"])
    seconds_since_previous = (
        candidates.groupby(["user_id", "_total"])["_ordered_at"].diff().dt.total_seconds()
    )
    duplicate_indexes = candidates[seconds_since_previous.between(0, 60, inclusive="both")].index
    return raw_orders.index.to_series().isin(duplicate_indexes)


def build_orders() -> pd.DataFrame:
    users = cleaned_users()
    valid_user_ids = set(users["user_id"].dropna().astype(str))
    country_by_user = users.set_index("user_id")["country"]

    raw = pd.read_csv(ORDERS_FILE, dtype={"order_id": "string", "user_id": "string"})

    order_id = clean_string(raw["order_id"])
    user_id = clean_string(raw["user_id"])
    ordered_at = to_utc(raw["created_at"])
    processed_at = to_utc(raw["processed_at"])
    total = pd.to_numeric(raw["total"], errors="coerce")
    status = raw["status"].astype("string").str.lower()
    channel = raw["channel"].astype("string").str.lower()

    valid = order_id.notna() & user_id.notna() & ordered_at.notna() & total.notna()
    valid &= user_id.astype(str).isin(valid_user_ids)
    valid &= ~channel.eq("staging")
    valid &= total.gt(0.5) & total.lt(5000)
    valid &= ~(processed_at.notna() & processed_at.lt(ordered_at))

    valid &= ~near_duplicate_mask(raw, valid)
    valid &= status.isin(["completed", "refunded"])

    country = user_id.map(country_by_user).fillna(normalize_country(raw["ip_country"]))
    net_sale_price = total.mask(status.eq("refunded"), 0.0).round(2)

    orders = pd.DataFrame(
        {
            "order_id": order_id,
            "user_id": user_id,
            "ordered_at": format_utc(ordered_at),
            "shipped_at": pd.NA,
            "net_sale_price": net_sale_price,
            "country": country,
        }
    )
    return orders[valid].drop_duplicates("order_id", keep="first").reset_index(drop=True)


def main() -> None:
    raw_rows = len(pd.read_csv(ORDERS_FILE, usecols=["order_id"]))
    staged = build_orders()
    output_path = write_stage_csv(staged, BUSINESS, "orders.csv")
    print_summary("PostgreSQL_1 orders", raw_rows, len(staged), output_path)


if __name__ == "__main__":
    main()
