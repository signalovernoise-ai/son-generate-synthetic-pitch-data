from __future__ import annotations

import pandas as pd

from synthetic_pitch_data.cleaning_common import (
    SOURCE_ROOT,
    TEST_REGEX,
    clean_string,
    format_utc,
    normalize_country,
    print_summary,
    test_pattern_mask,
    to_utc,
    write_stage_csv,
)


BUSINESS = "Shopify_2"
ORDERS_FILE = SOURCE_ROOT / BUSINESS / "shopify_orders_drinks.csv"
USERS_FILE = SOURCE_ROOT / BUSINESS / "shopify_customers_drinks.csv"


def cleaned_users() -> pd.DataFrame:
    raw_users = pd.read_csv(USERS_FILE, dtype={"customer_id": "string"})
    user_id = clean_string(raw_users["customer_id"])
    created_at = to_utc(raw_users["Created at"])

    valid = user_id.notna() & created_at.notna()
    valid &= ~test_pattern_mask(raw_users, ["Email", "First Name", "Last Name", "Tags"])

    users = pd.DataFrame({"user_id": user_id, "country": normalize_country(raw_users["Country"])})
    return users[valid].drop_duplicates("user_id", keep="first")


def duplicate_like_mask(raw_orders: pd.DataFrame, active_mask: pd.Series) -> pd.Series:
    candidates = raw_orders[active_mask].copy()
    candidates["_ordered_at"] = to_utc(candidates["Created at"])
    candidates["_email_norm"] = clean_string(candidates["Email"]).str.lower()
    candidates["_order_num"] = candidates["Name"].astype("string").str.extract(r"(\d+)")[0].astype("Int64")

    candidates = candidates.sort_values(["_email_norm", "_ordered_at", "_order_num"])
    seconds_since_previous = candidates.groupby("_email_norm")["_ordered_at"].diff().dt.total_seconds()
    previous_order_num = candidates.groupby("_email_norm")["_order_num"].shift()
    order_num_jump = candidates["_order_num"] - previous_order_num

    duplicate_indexes = candidates[
        seconds_since_previous.between(0, 300, inclusive="both") & order_num_jump.ge(1000)
    ].index
    return raw_orders.index.to_series().isin(duplicate_indexes)


def unique_order_id(order_id: pd.Series, user_id: pd.Series, ordered_at: pd.Series) -> pd.Series:
    result = order_id.copy()
    duplicated = result.duplicated(keep=False)
    result.loc[duplicated] = (
        result.loc[duplicated]
        + "|"
        + user_id.loc[duplicated].astype("string")
        + "|"
        + ordered_at.loc[duplicated].astype("string")
    )
    return result


def build_orders() -> pd.DataFrame:
    users = cleaned_users()
    valid_user_ids = set(users["user_id"].dropna().astype(str))
    country_by_user = users.set_index("user_id")["country"]

    raw = pd.read_csv(ORDERS_FILE, dtype={"Name": "string", "Customer ID": "string"})

    order_id = clean_string(raw["Name"])
    user_id = clean_string(raw["Customer ID"])
    ordered_at = to_utc(raw["Created at"])
    shipped_at = to_utc(raw["Fulfilled at"])
    total = pd.to_numeric(raw["Total"], errors="coerce")
    refunded_amount = pd.to_numeric(raw["Refunded Amount"], errors="coerce").fillna(0)
    financial_status = raw["Financial Status"].astype("string").str.lower()
    email_is_test = raw["Email"].astype("string").str.contains(TEST_REGEX, case=False, regex=True, na=False)

    valid = order_id.notna() & user_id.notna() & ordered_at.notna() & total.notna()
    valid &= user_id.astype(str).isin(valid_user_ids)
    valid &= ~email_is_test
    valid &= total.gt(0)
    valid &= financial_status.isin(["paid", "refunded", "partially_refunded"])
    valid &= ~duplicate_like_mask(raw, valid)

    formatted_ordered_at = format_utc(ordered_at)
    net_sale_price = (total - refunded_amount).round(2)
    net_sale_price = net_sale_price.mask(net_sale_price.abs().lt(0.005), 0.0)

    orders = pd.DataFrame(
        {
            "order_id": unique_order_id(order_id, user_id, formatted_ordered_at),
            "user_id": user_id,
            "ordered_at": formatted_ordered_at,
            "shipped_at": format_utc(shipped_at),
            "net_sale_price": net_sale_price,
            "country": user_id.map(country_by_user),
        }
    )
    return orders[valid].drop_duplicates("order_id", keep="first").reset_index(drop=True)


def main() -> None:
    raw_rows = len(pd.read_csv(ORDERS_FILE, usecols=["Name"]))
    staged = build_orders()
    output_path = write_stage_csv(staged, BUSINESS, "orders.csv")
    print_summary("Shopify_2 orders", raw_rows, len(staged), output_path)


if __name__ == "__main__":
    main()
