from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from synthetic_pitch_data.company.yumove.config import (
    BLOOMREACH_START,
    BUSINESS,
    CHANNEL_BREAK_WINDOWS,
    MONTHLY_AOV,
    MONTHLY_NEW_ORDER_SHARE,
    MONTHLY_ORDER_TARGETS,
    MONTHLY_REFUND_RATE,
    MONTHLY_SUBSCRIPTION_SHARE,
    PRODUCTS,
    PROMO_WINDOWS,
    ROW_SCALE,
    SEED,
    SOURCE_WINDOW_END,
    SOURCE_WINDOW_START,
    TRIPLE_WHALE_START,
)
from synthetic_pitch_data.paths import ensure_workspace_dirs
from synthetic_pitch_data.raw_common import print_source_summary, write_source_csv


FIRST_NAMES = [
    "Milo",
    "Poppy",
    "Charlie",
    "Ruby",
    "Bella",
    "Oscar",
    "Archie",
    "Rosie",
    "George",
    "Luna",
    "Freddie",
    "Teddy",
    "Olive",
    "Theo",
    "Maya",
    "Sophie",
    "Amelia",
    "Noah",
    "Hannah",
    "Eva",
]

LAST_NAMES = [
    "Smith",
    "Taylor",
    "Hughes",
    "Patel",
    "Morgan",
    "Davies",
    "Clark",
    "Hill",
    "Cooper",
    "Bennett",
    "Walker",
    "Turner",
    "Moore",
    "Wood",
    "Bailey",
]

CITIES = [
    ("London", "England", "ENG", "Greater London"),
    ("Manchester", "England", "ENG", "Greater Manchester"),
    ("Bristol", "England", "ENG", "Bristol"),
    ("Leeds", "England", "ENG", "West Yorkshire"),
    ("Birmingham", "England", "ENG", "West Midlands"),
    ("Edinburgh", "Scotland", "SCT", "City of Edinburgh"),
    ("Glasgow", "Scotland", "SCT", "Glasgow City"),
    ("Cardiff", "Wales", "WLS", "Cardiff"),
    ("Newcastle", "England", "ENG", "Tyne and Wear"),
    ("Southampton", "England", "ENG", "Hampshire"),
]

EMAIL_DOMAINS = [
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.co.uk",
    "icloud.com",
]

CHANNELS = [
    ("Paid Social", "facebook", "paid_social", "Facebook"),
    ("Paid Search", "google", "paid_search", "Google Ads"),
    ("Email", "bloomreach", "email", "Email"),
    ("Organic Search", "google", "organic", "Google"),
    ("Direct", "(direct)", "(none)", "Direct"),
    ("Affiliate", "impact", "affiliate", "Affiliate"),
]

# Acquisition-channel mix for a paid-heavy D2C brand. Aligned to CHANNELS order
# so paid social/search dominate rather than the unrealistic uniform split.
CHANNEL_WEIGHTS = [0.30, 0.24, 0.10, 0.15, 0.12, 0.09]

BROWSERS = ["Chrome", "Safari", "Firefox", "Edge"]
DEVICES = ["mobile", "desktop", "tablet"]
MONTH_KEYS = [str(month) for month in pd.period_range(SOURCE_WINDOW_START, SOURCE_WINDOW_END, freq="M")]


@dataclass
class CustomerProfile:
    customer_id: str
    canonical_email: str
    first_name: str
    last_name: str
    created_at: pd.Timestamp
    updated_at: pd.Timestamp
    city: str
    province: str
    province_code: str
    region: str
    postcode: str
    accepts_marketing: str | None
    acquisition_channel: str
    source: str
    medium: str
    source_platform: str
    segment: str
    primary_category: str
    promo_acquired: bool
    digest_bias: float
    email_drift: bool
    guest_fragmentation: bool


@dataclass
class SubscriptionRecord:
    subscription_id: str
    customer_id: str
    product_sku: str
    start_date: pd.Timestamp
    cancelled_at: pd.Timestamp | None
    quantity: int
    price: float


def month_keys() -> list[str]:
    return MONTH_KEYS


def to_iso(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def month_start(month_key: str) -> pd.Timestamp:
    return pd.Timestamp(f"{month_key}-01", tz="UTC")


def month_end(month_key: str) -> pd.Timestamp:
    return (month_start(month_key) + pd.offsets.MonthEnd(0)).tz_convert("UTC")


def random_timestamp_in_month(rng: np.random.Generator, month_key: str) -> pd.Timestamp:
    start = month_start(month_key)
    end = month_end(month_key) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)
    seconds = int((end - start).total_seconds())
    return start + pd.Timedelta(seconds=int(rng.integers(0, seconds + 1)))


def weighted_choice(
    rng: np.random.Generator,
    values: list[str],
    weights: list[float],
    size: int,
    replace: bool = True,
) -> np.ndarray:
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    return rng.choice(values, size=size, replace=replace, p=probs)


def make_email(first_name: str, last_name: str, serial: int, rng: np.random.Generator) -> str:
    domain = EMAIL_DOMAINS[int(rng.integers(0, len(EMAIL_DOMAINS)))]
    slug = f"{first_name}.{last_name}.{serial}".replace(" ", "").lower()
    return f"{slug}@{domain}"


def drift_email(email: str, rng: np.random.Generator) -> str:
    variant = int(rng.integers(0, 3))
    if variant == 0:
        return email.upper()
    if variant == 1:
        return f" {email.lower()} "
    local, domain = email.split("@", 1)
    return f"{local.title()}@{domain}"


def postcode(rng: np.random.Generator) -> str:
    outward = f"{chr(65 + int(rng.integers(0, 26)))}{int(rng.integers(1, 10))}"
    inward = f"{int(rng.integers(1, 10))}{chr(65 + int(rng.integers(0, 26)))}{chr(65 + int(rng.integers(0, 26)))}"
    return f"{outward} {inward}"


def slugify_title(value: str) -> str:
    slug = value.lower().replace("&", "and").replace("+", "plus").replace(",", "")
    slug = slug.replace("'", "").replace(".", "").replace("(", "").replace(")", "")
    slug = "-".join(slug.split())
    return slug


def category_family(category: str) -> str:
    if category.startswith("joint"):
        return "joint"
    if category.startswith("digestive"):
        return "digestive"
    if category.startswith("skin"):
        return "skin"
    if category.startswith("dental"):
        return "dental"
    if category.startswith("calming"):
        return "calming"
    if category.startswith("vitamins"):
        return "vitamins"
    return "bundle"


def build_products() -> pd.DataFrame:
    now = pd.Timestamp("2026-05-30", tz="UTC")
    rows: list[dict[str, object]] = []
    for idx, spec in enumerate(PRODUCTS, start=1):
        launch_ts = pd.Timestamp(spec.launch_date, tz="UTC")
        retire_ts = pd.Timestamp(spec.retire_date, tz="UTC") if spec.retire_date else pd.NaT
        if launch_ts > now:
            status = "draft"
        elif pd.notna(retire_ts) and retire_ts < now:
            status = "archived"
        elif not spec.current and pd.isna(retire_ts):
            status = "archived"
        else:
            status = "active"
        rows.append(
            {
                "product_id": f"gid://shopify/Product/{200000 + idx}",
                "admin_graphql_api_id": f"gid://shopify/Product/{200000 + idx}",
                "title": spec.title,
                "handle": slugify_title(spec.title),
                "vendor": "YuMOVE",
                "product_type": spec.category,
                "status": status,
                "published_at": to_iso(launch_ts if launch_ts < now else now),
                "created_at": to_iso(launch_ts),
                "updated_at": to_iso(now),
                "variant_id": f"gid://shopify/ProductVariant/{400000 + idx}",
                "sku": spec.sku,
                "barcode": f"{500000000000 + idx}",
                "option_1": "Default",
                "option_2": pd.NA,
                "option_3": pd.NA,
                "price": round(spec.base_price, 2),
                "compare_at_price": round(spec.compare_at_price, 2),
                "cost": round(spec.base_price * 0.34, 2),
                "inventory_quantity": int(500 + idx * 17),
            }
        )
    return pd.DataFrame(rows)


def active_products_for_date(ts: pd.Timestamp) -> list[dict[str, object]]:
    rows = []
    for idx, spec in enumerate(PRODUCTS, start=1):
        launch_ts = pd.Timestamp(spec.launch_date, tz="UTC")
        retire_ts = pd.Timestamp(spec.retire_date, tz="UTC") if spec.retire_date else None
        if ts < launch_ts:
            continue
        if retire_ts is not None and ts > retire_ts:
            continue
        rows.append(
            {
                "product_id": f"gid://shopify/Product/{200000 + idx}",
                "variant_id": f"gid://shopify/ProductVariant/{400000 + idx}",
                "sku": spec.sku,
                "title": spec.title,
                "category": spec.category,
                "family": category_family(spec.category),
                "base_price": spec.base_price,
                "compare_at_price": spec.compare_at_price,
                "subscription_eligible": spec.subscription_eligible,
            }
        )
    return rows


def promo_flags(ts: pd.Timestamp) -> dict[str, float]:
    flags = {"volume_lift": 1.0, "aov_multiplier": 1.0, "single_purchase": 0.0, "subscription_onboarding": 0.0}
    for window in PROMO_WINDOWS:
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        if start <= ts <= end:
            flags["volume_lift"] = max(flags["volume_lift"], window["volume_lift"])
            flags["aov_multiplier"] = min(flags["aov_multiplier"], window["aov_multiplier"])
            if window["promo_type"] == "single_purchase_discount":
                flags["single_purchase"] = 0.25
            if window["promo_type"] == "subscription_onboarding":
                flags["subscription_onboarding"] = 0.50
    return flags


def channel_break_share(ts: pd.Timestamp) -> float:
    baseline = 0.08
    for window in CHANNEL_BREAK_WINDOWS:
        start = pd.Timestamp(window["start"], tz="UTC")
        end = pd.Timestamp(window["end"], tz="UTC")
        if start <= ts <= end:
            return window["unattributed_share"]
    return baseline


def create_customer_profile(
    rng: np.random.Generator,
    serial: int,
    created_at: pd.Timestamp,
    promo_acquired: bool,
) -> CustomerProfile:
    first_name = FIRST_NAMES[int(rng.integers(0, len(FIRST_NAMES)))]
    last_name = LAST_NAMES[int(rng.integers(0, len(LAST_NAMES)))]
    city, province, province_code, region = CITIES[int(rng.integers(0, len(CITIES)))]
    email = make_email(first_name, last_name, serial, rng)
    acquisition = CHANNELS[int(rng.choice(len(CHANNELS), p=CHANNEL_WEIGHTS))]
    segment = rng.choice(["one_time", "repeat", "loyal"], p=[0.46, 0.36, 0.18])
    primary_category = rng.choice(["joint", "digestive"], p=[0.67, 0.33])
    accepts_marketing = rng.choice(["true", "false", "blank"], p=[0.56, 0.36, 0.08])
    return CustomerProfile(
        customer_id=str(1000000 + serial),
        canonical_email=email,
        first_name=first_name,
        last_name=last_name,
        created_at=created_at,
        updated_at=created_at + pd.Timedelta(days=int(rng.integers(3, 120))),
        city=city,
        province=province,
        province_code=province_code,
        region=region,
        postcode=postcode(rng),
        accepts_marketing=None if accepts_marketing == "blank" else accepts_marketing,
        acquisition_channel=acquisition[0],
        source=acquisition[1],
        medium=acquisition[2],
        source_platform=acquisition[3],
        segment=segment,
        primary_category=primary_category,
        promo_acquired=promo_acquired,
        digest_bias=0.62 if primary_category == "digestive" else 0.28,
        email_drift=bool(rng.random() < 0.022),
        guest_fragmentation=bool(rng.random() < 0.045),
    )


def category_weights(month_key: str) -> dict[str, float]:
    month_idx = MONTH_KEYS.index(month_key)
    month_progress = month_idx / max(1, (len(MONTH_KEYS) - 1))
    joint = 0.57 - (0.07 * month_progress)
    digestive = 0.20 + (0.08 * month_progress)
    skin = 0.08
    vitamins = 0.05
    dental = 0.04
    calming = 0.03
    bundle = 1.0 - joint - digestive - skin - vitamins - dental - calming
    return {
        "joint": joint,
        "digestive": digestive,
        "skin": skin,
        "vitamins": vitamins,
        "dental": dental,
        "calming": calming,
        "bundle": bundle,
    }


def choose_product_mix(
    rng: np.random.Generator,
    ts: pd.Timestamp,
    subscription_order: bool,
    digest_bias: float,
    target_aov: float,
) -> list[dict[str, object]]:
    active_products = active_products_for_date(ts)
    weights = category_weights(ts.strftime("%Y-%m"))
    items: list[dict[str, object]] = []
    gross_target = target_aov * (1.05 if subscription_order else 1.0)
    running_gross = 0.0
    while running_gross < gross_target and len(items) < 5:
        pool = []
        pool_weights = []
        customer_primary_is_digestive = digest_bias >= 0.5
        for product in active_products:
            family = str(product["family"])
            weight = weights.get(family, weights["bundle"])
            if family == "joint":
                weight *= max(0.45, 1.0 - digest_bias / 2)
            elif family == "digestive":
                weight *= 0.7 + digest_bias
            elif family in {"skin", "dental", "calming", "vitamins"}:
                weight *= 0.75 if customer_primary_is_digestive else 0.90
                if family == "vitamins" and ts >= pd.Timestamp("2025-02-01", tz="UTC"):
                    weight *= 1.15
            elif family == "bundle":
                weight *= 0.55 if subscription_order else 0.95
            category = str(product["category"])
            if "_cat_" in category or category.endswith("_cat") or category.startswith("calming_cat"):
                weight *= 0.16
            if "bulk" in category:
                weight *= 0.04
            if "working" in product["sku"].lower():
                weight *= 0.06
            if subscription_order and not product["subscription_eligible"] and rng.random() < 0.7:
                weight *= 0.15
            pool.append(product)
            pool_weights.append(weight)
        probs = np.array(pool_weights, dtype=float)
        probs = probs / probs.sum()
        choice = pool[int(rng.choice(len(pool), p=probs))]
        quantity = 1 if rng.random() < 0.82 else 2
        items.append({**choice, "quantity": quantity})
        running_gross += float(choice["compare_at_price"]) * quantity
    if not items:
        choice = active_products[0]
        items.append({**choice, "quantity": 1})
    return items


def create_order_and_items(
    rng: np.random.Generator,
    order_serial: int,
    line_item_serial: int,
    customer: CustomerProfile,
    ts: pd.Timestamp,
    subscription_order: bool,
    existing_subscription: SubscriptionRecord | None,
) -> tuple[dict[str, object], list[dict[str, object]], SubscriptionRecord | None]:
    month_key = ts.strftime("%Y-%m")
    promo = promo_flags(ts)
    target_aov = MONTHLY_AOV[month_key] * promo["aov_multiplier"]
    if subscription_order:
        target_aov *= 0.91
    elif customer.promo_acquired:
        target_aov *= 0.95

    items = choose_product_mix(rng, ts, subscription_order, customer.digest_bias, target_aov)
    line_rows: list[dict[str, object]] = []
    gross_line_total = 0.0
    discount_total = 0.0
    subscription_record = existing_subscription
    order_name = f"#YM{500000 + order_serial}"
    if rng.random() < 0.0025:
        order_name = f"#YM{499500 + int(rng.integers(1, 250))}"

    for item in items:
        list_price = float(item["compare_at_price"])
        sell_price = float(item["base_price"])
        quantity = int(item["quantity"])
        unit_discount = max(0.0, list_price - sell_price)
        if subscription_order and promo["subscription_onboarding"] > 0:
            first_cycle_discount = promo["subscription_onboarding"] if existing_subscription is None else 0.20
            sell_price = round(list_price * (1.0 - first_cycle_discount), 2)
            unit_discount = round(list_price - sell_price, 2)
        gross_line_total += list_price * quantity
        discount_total += unit_discount * quantity

        if subscription_order and item["subscription_eligible"] and subscription_record is None:
            sub_hash = hashlib.sha1(f"{customer.customer_id}|{item['sku']}".encode()).hexdigest()[:12]
            cancelled_at = None
            if rng.random() < 0.18:
                cancelled_at = ts + pd.Timedelta(days=int(rng.integers(90, 260)))
            subscription_record = SubscriptionRecord(
                subscription_id=f"sub_{sub_hash}",
                customer_id=customer.customer_id,
                product_sku=str(item["sku"]),
                start_date=ts,
                cancelled_at=cancelled_at,
                quantity=quantity,
                price=round(sell_price, 2),
            )

        line_rows.append(
            {
                "order_id": str(700000000 + order_serial),
                "line_item_id": f"gid://shopify/LineItem/{900000000 + line_item_serial}",
                "admin_graphql_api_id": f"gid://shopify/LineItem/{900000000 + line_item_serial}",
                "product_id": item["product_id"],
                "variant_id": item["variant_id"],
                "sku": item["sku"],
                "title": item["title"],
                "variant_title": "Default Title",
                "vendor": "YuMOVE",
                "product_type": item["category"],
                "quantity": quantity,
                "price": round(list_price, 2),
                "discounted_price": round(sell_price, 2),
                "total_discount": round(unit_discount * quantity, 2),
                "taxable": True,
                "requires_shipping": True,
                "fulfillment_status": "fulfilled",
                "selling_plan_name": "Subscribe & Save" if subscription_order and item["subscription_eligible"] else pd.NA,
                "selling_plan_id": (
                    f"sp_{hashlib.sha1(str(item['sku']).encode()).hexdigest()[:10]}"
                    if subscription_order and item["subscription_eligible"]
                    else pd.NA
                ),
            }
        )
        line_item_serial += 1

    total_line_items_price = round(gross_line_total, 2)
    total_discounts = round(discount_total, 2)
    total_price = round(max(0.5, total_line_items_price - total_discounts), 2)
    total_tax = round(total_price / 6.0, 2)
    refund_status = "none"
    refunded_amount = 0.0
    refund_rate = MONTHLY_REFUND_RATE[month_key]
    if customer.promo_acquired:
        refund_rate += 0.004
    if rng.random() < refund_rate:
        if rng.random() < 0.56:
            refund_status = "full"
            refunded_amount = total_price
            financial_status = "refunded"
        else:
            refund_status = "partial"
            refunded_amount = round(total_price * rng.uniform(0.20, 0.70), 2)
            financial_status = "partially_refunded"
    else:
        financial_status = "paid"

    order_row = {
        "id": str(700000000 + order_serial),
        "admin_graphql_api_id": f"gid://shopify/Order/{700000000 + order_serial}",
        "order_number": 500000 + order_serial,
        "name": order_name,
        "customer_id": customer.customer_id,
        "email": customer.canonical_email,
        "created_at": to_iso(ts),
        "processed_at": to_iso(ts + pd.Timedelta(minutes=int(rng.integers(2, 35)))),
        "updated_at": to_iso(ts + pd.Timedelta(hours=int(rng.integers(6, 96)))),
        "currency": "GBP",
        "presentment_currency": "GBP",
        "financial_status": financial_status,
        "fulfillment_status": "fulfilled",
        "subtotal_price": round(total_price, 2),
        "total_discounts": total_discounts,
        "total_tax": total_tax,
        "total_shipping_price_set_amount": 0.0,
        "total_price": total_price,
        "total_line_items_price": total_line_items_price,
        "taxes_included": True,
        "total_weight": int(220 * sum(int(item["quantity"]) for item in items)),
        "line_items_count": int(sum(int(item["quantity"]) for item in items)),
        "billing_address_country": "United Kingdom",
        "billing_address_country_code": "GB",
        "billing_address_city": customer.city,
        "billing_address_province": customer.province,
        "billing_address_zip": customer.postcode,
        "source_name": "web",
        "refunded_amount": round(refunded_amount, 2),
        "refund_status": refund_status,
    }
    return order_row, line_rows, subscription_record


def build_core_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    customer_profiles: dict[str, CustomerProfile] = {}
    active_customer_ids: list[str] = []
    subscription_registry: dict[str, SubscriptionRecord] = {}
    order_rows: list[dict[str, object]] = []
    line_rows: list[dict[str, object]] = []
    customer_serial = 1
    order_serial = 1
    line_item_serial = 1

    for month_key in month_keys():
        target_orders = int(round(MONTHLY_ORDER_TARGETS[month_key] * ROW_SCALE))
        new_count = int(round(target_orders * MONTHLY_NEW_ORDER_SHARE[month_key]))
        repeat_count = target_orders - new_count
        month_subscription_share = MONTHLY_SUBSCRIPTION_SHARE[month_key]

        for _ in range(new_count):
            ts = random_timestamp_in_month(rng, month_key)
            promo_acquired = bool(promo_flags(ts)["single_purchase"] or promo_flags(ts)["subscription_onboarding"])
            customer = create_customer_profile(rng, customer_serial, ts, promo_acquired)
            customer_profiles[customer.customer_id] = customer
            active_customer_ids.append(customer.customer_id)
            customer_serial += 1

            subscription_order = bool(rng.random() < (month_subscription_share * (1.12 if customer.primary_category == "digestive" else 0.86)))
            order_row, order_items, subscription = create_order_and_items(
                rng,
                order_serial,
                line_item_serial,
                customer,
                ts,
                subscription_order,
                subscription_registry.get(customer.customer_id),
            )
            order_rows.append(order_row)
            line_rows.extend(order_items)
            line_item_serial += len(order_items)
            if subscription is not None:
                subscription_registry[customer.customer_id] = subscription
            order_serial += 1

        if active_customer_ids and repeat_count > 0:
            eligible_ids = np.array(active_customer_ids, dtype=object)
            weights = []
            for customer_id in eligible_ids:
                customer = customer_profiles[str(customer_id)]
                base = {"one_time": 0.20, "repeat": 1.0, "loyal": 1.85}[customer.segment]
                if customer.customer_id in subscription_registry:
                    base *= 1.65
                if customer.promo_acquired and customer.customer_id not in subscription_registry:
                    base *= 0.88
                weights.append(base)
            chosen_ids = weighted_choice(
                rng,
                list(eligible_ids),
                weights,
                repeat_count,
                replace=True,
            )
            for customer_id in chosen_ids:
                customer = customer_profiles[str(customer_id)]
                ts = random_timestamp_in_month(rng, month_key)
                subscription_order = bool(
                    customer.customer_id in subscription_registry or rng.random() < (month_subscription_share * 1.05)
                )
                order_row, order_items, subscription = create_order_and_items(
                    rng,
                    order_serial,
                    line_item_serial,
                    customer,
                    ts,
                    subscription_order,
                    subscription_registry.get(customer.customer_id),
                )
                order_rows.append(order_row)
                line_rows.extend(order_items)
                line_item_serial += len(order_items)
                if subscription is not None:
                    subscription_registry[customer.customer_id] = subscription
                order_serial += 1

    buyer_count = len(customer_profiles)
    prospect_count = int(round(buyer_count * 0.18))
    for _ in range(prospect_count):
        month_key = weighted_choice(
            rng,
            MONTH_KEYS,
            [1.0] * len(MONTH_KEYS),
            size=1,
        )[0]
        ts = random_timestamp_in_month(rng, month_key)
        customer = create_customer_profile(rng, customer_serial, ts, promo_acquired=False)
        customer_profiles[customer.customer_id] = customer
        customer_serial += 1

    customers_df = build_shopify_customers(pd.DataFrame([vars(profile) for profile in customer_profiles.values()]), rng)
    orders_df = pd.DataFrame(order_rows).sort_values("created_at").reset_index(drop=True)
    order_items_df = pd.DataFrame(line_rows).reset_index(drop=True)
    subscriptions_df = build_ordergroove_subscriptions(list(subscription_registry.values()))
    return customers_df, orders_df, order_items_df, subscriptions_df, pd.DataFrame([vars(profile) for profile in customer_profiles.values()])


def build_shopify_customers(profiles: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for row in profiles.itertuples(index=False):
        display_email = drift_email(row.canonical_email, rng) if row.email_drift else row.canonical_email
        rows.append(
            {
                "id": row.customer_id,
                "email": display_email,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "phone": f"+44 7{int(rng.integers(100000000, 999999999))}",
                "created_at": to_iso(row.created_at),
                "updated_at": to_iso(max(row.updated_at, row.created_at)),
                "state": "enabled",
                "verified_email": True,
                "tax_exempt": False,
                "tags": "subscriber" if row.customer_id else "",
                "currency": "GBP",
                "accepts_marketing": row.accepts_marketing,
                "default_address_city": row.city,
                "default_address_province": row.province,
                "default_address_province_code": row.province_code,
                "default_address_country": "United Kingdom",
                "default_address_country_code": "GB",
                "default_address_zip": row.postcode,
            }
        )
    return pd.DataFrame(rows).sort_values("created_at").reset_index(drop=True)


def build_ordergroove_subscriptions(subscriptions: list[SubscriptionRecord]) -> pd.DataFrame:
    rows = []
    for idx, subscription in enumerate(subscriptions, start=1):
        rows.append(
            {
                "publicId": subscription.subscription_id,
                "externalId": f"ext_{subscription.subscription_id}",
                "subscriptionType": "subscribe_and_save",
                "live": subscription.cancelled_at is None,
                "quantity": subscription.quantity,
                "price": round(subscription.price, 2),
                "currencyCode": "GBP",
                "frequencyDays": 30,
                "every": 1,
                "everyPeriod": 3,
                "productSku": subscription.product_sku,
                "startDate": subscription.start_date.date().isoformat(),
                "cancelled": (
                    subscription.cancelled_at.date().isoformat()
                    if subscription.cancelled_at is not None
                    else pd.NA
                ),
                "cancelReason": "Changed routine" if subscription.cancelled_at is not None else pd.NA,
                "cancelReasonCode": "customer_choice" if subscription.cancelled_at is not None else pd.NA,
                "sessionId": f"ogs_{10000 + idx}",
                "merchantOrderId": pd.NA,
                "offerPublicId": f"offer_{idx}",
                "created": to_iso(subscription.start_date),
                "updated": to_iso(subscription.cancelled_at if subscription.cancelled_at is not None else subscription.start_date + pd.Timedelta(days=40)),
                "extraData": f'{{"customer_id":"{subscription.customer_id}","sku":"{subscription.product_sku}"}}',
                "reminderDays": 5,
            }
        )
    return pd.DataFrame(rows)


def build_ordergroove_subscription_orders(orders: pd.DataFrame, subscriptions: pd.DataFrame, order_items: pd.DataFrame) -> pd.DataFrame:
    sub_line_items = order_items[order_items["selling_plan_id"].notna()][["order_id", "sku", "selling_plan_id"]].drop_duplicates()
    merged = orders.merge(sub_line_items, left_on="id", right_on="order_id", how="inner")
    sku_to_sub = dict(zip(subscriptions["productSku"], subscriptions["publicId"]))
    rows = []
    for idx, row in enumerate(merged.itertuples(index=False), start=1):
        rows.append(
            {
                "publicId": f"ogo_{idx:08d}",
                "status": "success" if row.financial_status == "paid" else "partial_refund",
                "subTotal": row.subtotal_price,
                "taxTotal": row.total_tax,
                "shippingTotal": row.total_shipping_price_set_amount,
                "discountTotal": row.total_discounts,
                "total": row.total_price,
                "place": "shopify",
                "created": row.created_at,
                "updated": row.updated_at,
                "cancelled": pd.NA,
                "orderMerchantId": row.id,
                "rejectedMessage": pd.NA,
                "extraData": f'{{"subscription_id":"{sku_to_sub.get(row.sku, "")}"}}',
                "locked": False,
                "oosFreeShipping": False,
                "currencyCode": "GBP",
                "tries": 1,
                "genericErrorCount": 0,
                "merchantPublicId": f"merchant_{row.customer_id}",
                "hasPlan": True,
            }
        )
    return pd.DataFrame(rows)


def build_ordergroove_events(subscriptions: pd.DataFrame, subscription_orders: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in subscriptions.itertuples(index=False):
        rows.append(
            {
                "id": f"evt_{row.publicId}_create",
                "type": "subscription.create",
                "created": row.created,
                "object_type": "subscription",
                "merchant": "yumove",
                "public_id": row.publicId,
            }
        )
        if pd.notna(row.cancelled):
            rows.append(
                {
                    "id": f"evt_{row.publicId}_cancel",
                    "type": "subscription.cancel",
                    "created": pd.Timestamp(row.cancelled).strftime("%Y-%m-%dT00:00:00Z"),
                    "object_type": "subscription",
                    "merchant": "yumove",
                    "public_id": row.publicId,
                }
            )
    for row in subscription_orders.head(50000).itertuples(index=False):
        rows.append(
            {
                "id": f"evt_{row.publicId}_success",
                "type": "order.success",
                "created": row.created,
                "object_type": "order",
                "merchant": "yumove",
                "public_id": row.publicId,
            }
        )
    return pd.DataFrame(rows)


def assign_attribution(
    rng: np.random.Generator,
    customer_source: str,
    customer_medium: str,
    customer_channel: str,
    ts: pd.Timestamp,
) -> tuple[str, str, str, str, str, str, str, str]:
    if rng.random() < channel_break_share(ts):
        return (
            "Unassigned",
            "Unassigned",
            "(direct)",
            "(none)",
            "(direct) / (none)",
            "Direct",
            "(direct)",
            "(none)",
        )
    if rng.random() < 0.015:
        return (
            "Unassigned",
            "Unassigned",
            "(not set)",
            "(not set)",
            "(not set) / (not set)",
            "Unassigned",
            "(not set)",
            "(not set)",
        )
    session_channel = customer_channel
    session_source = customer_source
    session_medium = customer_medium
    return (
        customer_channel,
        session_channel,
        customer_source,
        customer_medium,
        f"{customer_source} / {customer_medium}",
        "Web",
        session_source,
        session_medium,
    )


def build_ga4_orders(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    order_items: pd.DataFrame,
    profiles: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED + 11)
    profile_map = profiles.set_index("customer_id").to_dict("index")
    item_map = {
        str(order_id): group.to_dict("records")
        for order_id, group in order_items.groupby("order_id", sort=False)
    }
    order_rows = []
    item_rows = []
    for order in orders.itertuples(index=False):
        created_at = pd.Timestamp(order.created_at)
        order_ts = created_at + pd.Timedelta(minutes=int(rng.integers(-18, 18)))
        profile = profile_map[str(order.customer_id)]
        channels = assign_attribution(
            rng,
            str(profile["source"]),
            str(profile["medium"]),
            str(profile["acquisition_channel"]),
            order_ts,
        )
        promo_name = "25% Single Purchase" if pd.Timestamp("2026-05-18T00:00:00Z") <= order_ts <= pd.Timestamp("2026-06-01T23:59:59Z") else pd.NA
        items = item_map[str(order.id)]
        gross_item_revenue = round(sum(float(item["price"]) * int(item["quantity"]) for item in items), 2)
        item_revenue = round(sum(float(item["discounted_price"]) * int(item["quantity"]) for item in items), 2)
        order_rows.append(
            {
                "date": order_ts.strftime("%Y%m%d"),
                "dateHour": order_ts.strftime("%Y%m%d%H"),
                "dateHourMinute": order_ts.strftime("%Y%m%d%H%M"),
                "transactionId": order.id,
                "defaultChannelGroup": channels[0],
                "sessionDefaultChannelGroup": channels[1],
                "source": channels[2],
                "medium": channels[3],
                "sourceMedium": channels[4],
                "sourcePlatform": channels[5],
                "sessionSource": channels[6],
                "sessionMedium": channels[7],
                "sessionSourceMedium": f"{channels[6]} / {channels[7]}",
                "sessionSourcePlatform": "Web",
                "browser": BROWSERS[int(rng.integers(0, len(BROWSERS)))],
                "deviceCategory": DEVICES[int(rng.integers(0, len(DEVICES)))],
                "platformDeviceCategory": DEVICES[int(rng.integers(0, len(DEVICES)))],
                "country": "United Kingdom",
                "region": str(profile["region"]),
                "city": order.billing_address_city,
                "streamId": "149905001",
                "platform": "web",
                "user_id": order.customer_id if rng.random() < 0.88 else pd.NA,
                "itemPromotionId": "promo_single_25" if pd.notna(promo_name) else pd.NA,
                "itemPromotionName": promo_name,
                "purchaseRevenue": round(order.total_price - order.refunded_amount, 2),
                "grossPurchaseRevenue": order.total_price,
                "shippingAmount": order.total_shipping_price_set_amount,
                "taxAmount": order.total_tax,
                "itemRevenue": item_revenue,
                "grossItemRevenue": gross_item_revenue,
                "transactions": 1,
                "ecommercePurchases": 1,
            }
        )
        for item in items:
            item_rows.append(
                {
                    "date": order_ts.strftime("%Y%m%d"),
                    "dateHour": order_ts.strftime("%Y%m%d%H"),
                    "dateHourMinute": order_ts.strftime("%Y%m%d%H%M"),
                    "transactionId": order.id,
                    "itemId": item["sku"],
                    "itemName": item["title"],
                    "itemBrand": "YuMOVE",
                    "itemVariant": "Default Title",
                    "itemCategory": item["product_type"],
                    "itemCategory2": pd.NA,
                    "itemCategory3": pd.NA,
                    "itemCategory4": pd.NA,
                    "itemCategory5": pd.NA,
                    "itemListId": "pdp",
                    "itemListName": "Product Detail Page",
                    "itemPromotionId": "promo_single_25" if pd.notna(promo_name) else pd.NA,
                    "itemPromotionName": promo_name,
                    "itemRevenue": round(float(item["discounted_price"]) * int(item["quantity"]), 2),
                    "grossItemRevenue": round(float(item["price"]) * int(item["quantity"]), 2),
                    "itemRefundAmount": round(order.refunded_amount / max(1, len(items)), 2) if order.refunded_amount else 0.0,
                    "itemDiscountAmount": round(float(item["total_discount"]), 2),
                    "itemsPurchased": int(item["quantity"]),
                    "itemPurchaseQuantity": int(item["quantity"]),
                }
            )
    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)


def build_bloomreach_events(orders: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 23)
    bloomreach_start = pd.Timestamp(BLOOMREACH_START, tz="UTC")
    recent_orders = orders[pd.to_datetime(orders["created_at"]) >= bloomreach_start].copy()
    profile_map = profiles.set_index("customer_id").to_dict("index")
    campaign_rows = []
    statuses = ["sent", "delivered", "opened", "clicked"]
    sms_statuses = ["sent", "delivered", "clicked"]
    for idx, order in enumerate(recent_orders.itertuples(index=False), start=1):
        if rng.random() > 0.35:
            continue
        profile = profile_map[str(order.customer_id)]
        action_type = "email" if rng.random() < 0.78 else "sms"
        base_ts = max(
            bloomreach_start,
            pd.Timestamp(order.created_at) - pd.Timedelta(days=int(rng.integers(1, 14))),
        )
        chosen_statuses = statuses if action_type == "email" else sms_statuses
        for status_idx, status in enumerate(chosen_statuses):
            status_value = status.upper() if status == "clicked" and rng.random() < 0.08 else status
            campaign_rows.append(
                {
                    "timestamp": to_iso(base_ts + pd.Timedelta(minutes=status_idx * 15)),
                    "status": status_value,
                    "campaign_name": (
                        "Digestive Welcome Journey" if profile["primary_category"] == "digestive" else "Joint Care Replenishment"
                    ),
                    "campaign_id": f"cmp_{1000 + idx % 17}",
                    "action_type": action_type,
                    "action_name": "post_purchase_flow",
                    "action_id": f"act_{200 + idx % 9}",
                    "integration_id": "br_yumove_uk",
                    "integration_name": "Bloomreach Engagement",
                    "integration_type": "engagement",
                    "campaign_policy": "opt_in",
                    "consent_category": "marketing",
                    "subject": "Keep them moving with YuMOVE",
                    "language": "en-GB",
                    "recipient": drift_email(profile["canonical_email"], rng) if profile["email_drift"] else profile["canonical_email"],
                    "sent_timestamp": to_iso(base_ts),
                    "message": "Tailored lifecycle message",
                    "message_id": f"msg_{idx}_{status_idx}",
                    "comment": pd.NA,
                    "error": pd.NA,
                    "code": pd.NA,
                    "cumulative": status_idx + 1,
                    "ip": f"81.2.{int(rng.integers(0,255))}.{int(rng.integers(1,255))}",
                    "user-agent": "Mozilla/5.0",
                    "url": "https://yumove.co.uk/pages/yumove-subscription" if status == "clicked" else pd.NA,
                    "city": profile["city"],
                    "country": "United Kingdom",
                    "number_of_message_parts": 1,
                    "sender": "YuMOVE",
                    "status_code": 200,
                    "preset_channel": "EMAIL" if action_type == "email" and rng.random() < 0.05 else action_type,
                    "platform": "shopify",
                }
            )
    return pd.DataFrame(campaign_rows)


def build_zendesk_tickets(orders: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 31)
    profile_map = profiles.set_index("customer_id").to_dict("index")
    ticket_rows = []
    issue_subjects = [
        ("Subscription timing question", "normal_delivery"),
        ("How should I use this product?", "product_usage"),
        ("Order update", "delivery_tracking"),
        ("Digestive product question", "digestive_query"),
        ("Joint care dosage question", "joint_query"),
    ]
    order_sample = orders.sample(frac=0.11, random_state=SEED).reset_index(drop=True)
    for idx, order in enumerate(order_sample.itertuples(index=False), start=1):
        profile = profile_map[str(order.customer_id)]
        subject, tag = issue_subjects[int(rng.integers(0, len(issue_subjects)))]
        created_at = pd.Timestamp(order.created_at) + pd.Timedelta(days=int(rng.integers(1, 14)))
        updated_at = created_at + pd.Timedelta(hours=int(rng.integers(2, 96)))
        ticket_rows.append(
            {
                "id": 800000 + idx,
                "created_at": to_iso(created_at),
                "updated_at": to_iso(updated_at),
                "status": "open" if rng.random() < 0.22 else "solved",
                "priority": weighted_choice(rng, ["normal", "high", "urgent"], [0.78, 0.18, 0.04], 1)[0],
                "type": "question",
                "subject": subject,
                "description": f"Pet owner support query linked to order {order.name}.",
                "requester_id": int(order.customer_id),
                "submitter_id": int(order.customer_id),
                "assignee_id": 9000 + int(rng.integers(1, 35)),
                "organization_id": 1,
                "group_id": 100 + int(rng.integers(1, 8)),
                "via_channel": weighted_choice(rng, ["email", "web"], [0.74, 0.26], 1)[0],
                "ticket_form_id": 501,
                "brand_id": 7001,
                "recipient": profile["canonical_email"],
                "tags": f"pet_owner,{tag}",
                "satisfaction_score": weighted_choice(rng, ["good", "bad", "offered"], [0.72, 0.05, 0.23], 1)[0],
            }
        )
        if rng.random() < 0.003:
            dup = ticket_rows[-1].copy()
            dup["id"] = 880000 + idx
            dup["updated_at"] = to_iso(updated_at + pd.Timedelta(minutes=8))
            ticket_rows.append(dup)
    return pd.DataFrame(ticket_rows)


def build_triple_whale(orders: pd.DataFrame, profiles: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED + 41)
    start_ts = pd.Timestamp(TRIPLE_WHALE_START, tz="UTC")
    recent_orders = orders[pd.to_datetime(orders["created_at"]) >= start_ts].copy()
    profile_map = profiles.set_index("customer_id").to_dict("index")
    order_rows = []
    journey_rows = []
    for idx, order in enumerate(recent_orders.itertuples(index=False), start=1):
        profile = profile_map[str(order.customer_id)]
        order_ts = pd.Timestamp(order.created_at)
        # Partial attribution coverage: ~8% of orders exist in commerce but were
        # never captured by Triple Whale, leaving a genuine join gap downstream.
        if rng.random() < 0.08:
            continue
        base_channel, _, source, medium, _, _, _, _ = assign_attribution(
            rng,
            str(profile["source"]),
            str(profile["medium"]),
            str(profile["acquisition_channel"]),
            order_ts,
        )
        coverage = rng.random()
        if coverage < 0.06:
            channel = "unattributed"
            source_name = "(not set)"
            utm_source = "(not set)"
            utm_medium = "(not set)"
        else:
            channel = base_channel
            source_name = source
            utm_source = source
            utm_medium = medium
        duplicate_order_rows = 2 if rng.random() < 0.06 else 1
        for dup in range(duplicate_order_rows):
            order_rows.append(
                {
                    "shop_id": "yumove_uk",
                    "shop_name": "YuMOVE UK",
                    "order_id": order.id,
                    "order_name": order.name,
                    "created_at": order.created_at,
                    "currency": "GBP",
                    "customer_id": order.customer_id,
                    "customer_email": profile["canonical_email"],
                    "session_id": f"tw_sess_{idx:08d}",
                    "triple_id": f"triple_{idx:08d}_{dup}",
                    "channel": channel,
                    "campaign_id": f"cmp_{1500 + idx % 23}",
                    "campaign_name": "Digestive Scaling Push" if profile["primary_category"] == "digestive" else "Joint Care Always On",
                    "ad_id": f"ad_{20000 + idx % 101}",
                    "adset_id": f"adset_{3000 + idx % 71}",
                    "source_name": source_name,
                    "utm_source": utm_source,
                    "utm_medium": utm_medium,
                    "click_ts": to_iso(order_ts - pd.Timedelta(hours=int(rng.integers(1, 72)))),
                    "model": "total_impact",
                    "is_new_customer": dup == 0 and rng.random() < 0.5,
                }
            )
        step_count = int(weighted_choice(rng, ["2", "3", "4"], [0.36, 0.42, 0.22], 1)[0])
        for step in range(step_count):
            event_ts = order_ts - pd.Timedelta(hours=(step_count - step) * int(rng.integers(6, 30)))
            journey_rows.append(
                {
                    "order_id": order.id,
                    "session_id": f"tw_sess_{idx:08d}",
                    "triple_id": f"triple_{idx:08d}_0",
                    "customer_id": order.customer_id,
                    "email": profile["canonical_email"],
                    "event_time": to_iso(event_ts),
                    "type": weighted_choice(rng, ["page_view", "product_view", "landing_page", "purchase"], [0.35, 0.30, 0.20, 0.15], 1)[0],
                    "event_name": "product_page_view" if step < step_count - 1 else "purchase",
                    "source": source_name,
                    "referrer": "https://www.google.com/" if source_name == "google" else "https://facebook.com/",
                    "url": f"https://yumove.co.uk/products/{slugify_title(PRODUCTS[idx % len(PRODUCTS)].title)}",
                    "query_params": f"utm_source={utm_source}&utm_medium={utm_medium}",
                    "page_type": "product",
                    "product_id": order.id if step == step_count - 1 else f"gid://shopify/Product/{200001 + idx % len(PRODUCTS)}",
                    "product_name": PRODUCTS[idx % len(PRODUCTS)].title,
                    "device": DEVICES[int(rng.integers(0, len(DEVICES)))],
                    "lead_click_ts": to_iso(event_ts - pd.Timedelta(minutes=int(rng.integers(20, 160)))),
                    "is_new_customer": bool(rng.random() < 0.5),
                    "subscription_id": pd.NA,
                }
            )
    return pd.DataFrame(order_rows), pd.DataFrame(journey_rows)


def write_outputs(output_map: dict[str, pd.DataFrame]) -> None:
    for filename, df in output_map.items():
        output_path = write_source_csv(df, BUSINESS, filename)
        print_source_summary(f"{BUSINESS} {filename}", len(df), output_path)


def main() -> None:
    ensure_workspace_dirs()
    products_df = build_products()
    customers_df, orders_df, order_items_df, subscriptions_df, profiles_df = build_core_sources()
    subscription_orders_df = build_ordergroove_subscription_orders(orders_df, subscriptions_df, order_items_df)
    ordergroove_events_df = build_ordergroove_events(subscriptions_df, subscription_orders_df)
    ga4_orders_df, ga4_items_df = build_ga4_orders(orders_df, customers_df, order_items_df, profiles_df)
    bloomreach_df = build_bloomreach_events(orders_df, profiles_df)
    zendesk_df = build_zendesk_tickets(orders_df, profiles_df)
    triple_whale_orders_df, triple_whale_journey_df = build_triple_whale(orders_df, profiles_df)

    write_outputs(
        {
            "shopify_products.csv": products_df,
            "shopify_orders.csv": orders_df,
            "shopify_customers.csv": customers_df,
            "shopify_order_items.csv": order_items_df,
            "ordergroove_subscriptions.csv": subscriptions_df,
            "ordergroove_subscription_orders.csv": subscription_orders_df,
            "ordergroove_events.csv": ordergroove_events_df,
            "ga4_reporting_purchase_events.csv": ga4_orders_df,
            "ga4_reporting_purchase_items.csv": ga4_items_df,
            "bloomreach_campaign_events.csv": bloomreach_df,
            "zendesk_tickets.csv": zendesk_df,
            "triple_whale_attributed_orders.csv": triple_whale_orders_df,
            "triple_whale_customer_journey_events.csv": triple_whale_journey_df,
        }
    )


if __name__ == "__main__":
    main()
