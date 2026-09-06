"""Constants, catalog and monthly target series for Sunna Supplements.

Grounded in the live sunnasupplements.com Shopify storefront (products.json, 2026-08-13) and
the approved trajectory in
skills/company-synthetic-data-workflow/assets/company-setups/sunna.yaml.

Two things drive this company and differ from previous ones:

1. **Islamic-calendar seasonality that migrates.** Ramadan is the peak trading window and it
   starts ~11 days earlier every year, so the peak month walks backwards across the window
   (Mar 2025 -> Feb/Mar 2026 -> Feb 2027). Seasonality is baked into MONTHLY_ORDER_TARGETS,
   not applied as a separate multiplier.

2. **Multi-month supplies are variants, not baskets.** A "3 Months" supply is ONE order line
   at a list-price discount, so order-item rows per order stay close to 1 and AOV is driven by
   the supply-tier mix rather than by units per order.
"""

from __future__ import annotations

from dataclasses import dataclass


BUSINESS = "sunna"
SEED = 20260813
# Full-scale build projects ~3.7m raw rows, below the 5m gate, so neither a window cut nor
# operational row scaling is applied. Rates are scale-invariant; products are never scaled.
ROW_SCALE = 1.0

# Default modeling window: 18 historic + 6 future months (today 2026-08-13).
SOURCE_WINDOW_START = "2025-03-01"
SOURCE_WINDOW_END = "2027-02-28"

# Source-specific windows.
KLAVIYO_START = "2025-09-01"        # email/SMS stream trimmed to the last 12 historic months
GOOGLE_ADS_START = "2025-03-01"     # full window
META_ADS_START = "2025-03-01"       # full window
TIKTOK_ADS_START = "2025-03-01"     # full window

# Evidenced catalog launches (products.json published_at, pulled 2026-08-13).
LAUNCH_RANGE_WAVE = "2025-07-12"     # Black Seed Oil, Electrolytes, Sachets, Mango Lassi
LAUNCH_CREATINE = "2025-10-31"       # move into sports nutrition
LAUNCH_DUO_BUNDLES = "2025-11-26"    # Electrolytes Duo, Creatine Duo
LAUNCH_IMMUNITY = "2025-12-01"       # Iron Complex, Halal Immunity, Black Seed Oil Softgels
LAUNCH_PROBIOTIC = "2026-04-01"

# Ramadan / Eid. The Islamic calendar drifts ~11 days earlier each Gregorian year, which is
# why the peak month moves. Dates are the observed UK start dates.
#   Ramadan 1446: 2025-03-01 -> 2025-03-29, Eid al-Fitr 2025-03-30
#   Ramadan 1447: 2026-02-18 -> 2026-03-19, Eid al-Fitr 2026-03-20
#   Ramadan 1448: 2027-02-08 -> 2027-03-09, Eid al-Fitr 2027-03-10
RAMADAN_WINDOWS = [
    ("2025-03-01", "2025-03-30"),
    ("2026-02-18", "2026-03-20"),
    ("2027-02-08", "2027-02-28"),   # clipped at the window end
]
# Months carrying meaningful Ramadan trade — used to shift the supply-tier mix toward bulk.
RAMADAN_MONTHS = {"2025-03", "2026-02", "2026-03", "2027-01", "2027-02"}
# Bulk buying in Ramadan suppresses the next few months of repeat purchasing.
RAMADAN_BULK_SHIFT = 0.22          # extra probability mass moved onto 3/6-month supplies
BULK_REPEAT_SUPPRESSION_MONTHS = {1: 0, 3: 4, 6: 7}   # supply months -> months of repeat delay

# Channel-tracking break windows.
TRACKING_BREAKS = [
    ("2025-11-03", 9, 0.22),   # US store launch + EasyLocation geo-redirect intercepting sessions
    ("2026-11-23", 7, 0.20),   # Black Friday tagging change through GTM-5CCVD6QR
]
UNATTRIBUTED_BASELINE = 0.08

# UK VAT: supplements are standard-rated; prices on site are VAT-inclusive.
VAT_RATE = 0.20

# Delivery: blanket free 24h tracked shipping, NO spend threshold. Shipping is 0.00 on every
# order, so there is no basket-bunching effect and no GA4-vs-Shopify shipping revenue gap.
SHIPPING_STANDARD = 0.00

# Skio Subscribe & Save. The live PDP exposes two selling-plan groups: 20% on hero SKUs and
# 10% elsewhere, each at 1 / 3 / 6-month delivery intervals.
SUB_DISCOUNT_HERO = 0.20
SUB_DISCOUNT_STANDARD = 0.10
# Take-rate ramps as Skio matures (0.17 -> 0.22 of first orders).
SUB_TAKE_RATE_START = 0.17
SUB_TAKE_RATE_END = 0.22
SUB_TAKE_RATE_BLACK_FRIDAY_FACTOR = 0.86   # discount-led November cohorts convert worse

# Order-mix controls. Acquisition-led brand: new orders dominate, unlike Fussy.
ADHOC_REPEAT_SHARE_START = 0.20
ADHOC_REPEAT_SHARE_END = 0.25
MIN_NEW_SHARE = 0.43           # floor share of monthly orders that are new acquisitions

# Renewal survival by cycle index. Calibrated to ~2.0 renewals per subscriber before
# censoring, which lands realized renewals-per-subscriber in the documented 1.6-2.1 band
# once the window edge and monthly capacity are applied.
RENEWAL_SURVIVAL = {1: 0.82, 2: 0.76, 3: 0.72, 4: 0.68}
RENEWAL_SURVIVAL_TAIL = 0.66

# Welcome offer: 10% off the first order, captured through the Klaviyo onsite form.
WELCOME_DISCOUNT = 0.10
WELCOME_TAKE_RATE = 0.40

# Data-issue prevalences (see sunna.yaml data_issues).
EMAIL_DRIFT_RATE = 0.022            # check: email_casing_or_whitespace_drift  [0.015, 0.030]
DUPLICATE_ORDER_NAME_RATE = 0.003   # check: near_duplicate_orders             [0.0015, 0.0045]
TEST_ORDER_RATE = 0.0022            # ~0.15-0.30% of orders
GA4_RENEWAL_CAPTURE = 0.08          # share of renewals that still reach GA4 (Direct/(not set))
GA4_WEB_LOSS = 0.08                 # tag/consent loss on genuine web checkouts
CANCEL_LAG_RATE = 0.15              # share of cancels recorded well after the last charge
# Navidium and gift lines are CHECKOUT upsells, so they never attach to a server-side
# subscription renewal. These rates are therefore applied to web-checkout orders only; the
# all-orders prevalence lands ~20% lower, and the gift SKUs only exist from 2025-10-16.
NAVIDIUM_ATTACH_RATE = 0.20         # of web-checkout orders
GIFT_LINE_RATE = 0.19               # of web-checkout orders, post gift-SKU launch
INTELLIGEMS_TEST_RATE = 0.075       # share of lines on tested SKUs at a non-catalog price
INTELLIGEMS_TESTED_SKUS = {
    "SUN-COLLAGEN-1M", "SUN-COLLAGEN-3M", "SUN-ELECTRO-1M", "SUN-CREATINE-1M",
    "SUN-IMMUNITY-1M", "SUN-MARINE-1M",
}
KLAVIYO_US_PROFILE_RATE = 0.10      # profiles from the US store with no UK Shopify customer
GORGIAS_NO_ORDER_RATE = 0.33
GORGIAS_NO_CUSTOMER_RATE = 0.09


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    title: str
    option_1: str          # the Shopify variant option (supply size / colour)
    product_key: str       # groups variants of the same product
    product_type: str
    role: str              # drives basket construction
    base_price: float
    compare_at_price: float
    subscription_eligible: bool
    sub_discount: float
    supply_months: int     # 1 / 3 / 6; 0 for accessories, gifts and shipping protection
    current: bool
    launch_date: str
    retire_date: str | None = None


# (product_key, title, product_type, hero?, launch, [(option, price, compare_at, months)])
_SUPPLEMENTS = [
    ("COLLAGEN", "Halal Collagen Protein", "Collagen", True, "2024-11-29", [
        ("1 Pouch", 25.00, 25.00, 1), ("3 Pouches", 56.25, 75.00, 3), ("6 Pouches", 99.97, 150.00, 6)]),
    ("MARINE", "Marine Collagen", "Collagen", True, "2024-12-06", [
        ("1 Month", 30.00, 30.00, 1), ("3 Months", 78.00, 90.00, 3), ("6 Months", 144.00, 180.00, 6)]),
    ("OMEGA3", "Omega 3 Fish Oil", "Essential Fatty Acids", False, "2024-12-06", [
        ("1 Month Supply", 30.00, 30.00, 1), ("3 Months", 59.99, 90.00, 3), ("6 Months", 118.00, 180.00, 6)]),
    ("D3K2", "Vitamin D3 & K2 MK-7 with MCT Oil", "Vitamins", False, "2024-12-06", [
        ("1 Month Supply", 25.00, 25.00, 1), ("3 Months", 49.99, 75.00, 3), ("6 Months", 89.99, 150.00, 6)]),
    ("TURMERIC", "Turmeric Complex", "Herbal", False, "2024-12-06", [
        ("1 Month Supply", 25.00, 25.00, 1), ("3 Months", 49.99, 75.00, 3), ("6 Months", 89.99, 150.00, 6)]),
    ("MAGNESIUM", "Magnesium Complex", "Minerals", False, "2024-12-06", [
        ("1 Month Supply", 25.00, 25.00, 1), ("3 Months", 49.99, 75.00, 3), ("6 Months", 89.99, 150.00, 6)]),
    ("BLACKSEED", "Black Seed Oil", "Herbal", False, LAUNCH_RANGE_WAVE, [
        ("Black Seed Oil", 20.00, 20.00, 1), ("3 Months", 55.00, 60.00, 3), ("6 Months", 100.00, 120.00, 6)]),
    ("SACHETS", "Halal Collagen Protein Sachets", "Collagen", True, LAUNCH_RANGE_WAVE, [
        ("1 Box", 15.00, 15.00, 1), ("3 Boxes", 37.50, 45.00, 3), ("6 Boxes", 60.00, 90.00, 6)]),
    ("MANGOLASSI", "Mango Lassi Collagen Drink with Vitamin C", "Collagen", True, LAUNCH_RANGE_WAVE, [
        ("2 Weeks", 33.00, 33.00, 1), ("6 Weeks", 78.00, 99.00, 3), ("3 Months", 132.00, 198.00, 6)]),
    ("ELECTRO", "Electrolytes - Tropical Refresh", "Hydration", False, LAUNCH_RANGE_WAVE, [
        ("Tropical Refresh", 35.00, 35.00, 1), ("3 Months", 99.00, 105.00, 3), ("6 Months", 180.00, 211.76, 6)]),
    ("CREATINE", "Creatine Monohydrate - Unflavoured", "Sports Nutrition", False, LAUNCH_CREATINE, [
        ("1 Month", 25.00, 25.00, 1), ("3 Months", 56.25, 60.00, 3), ("6 Months", 99.97, 90.00, 6)]),
    ("IRON", "Iron Complex", "Minerals", False, LAUNCH_IMMUNITY, [
        ("1 Bottle", 25.00, 25.00, 1), ("3 Bottles", 56.25, 75.00, 3), ("6 Bottles", 99.99, 150.00, 6)]),
    ("IMMUNITY", "Halal Immunity", "Vitamins", False, LAUNCH_IMMUNITY, [
        ("1 Month Supply", 19.99, 25.00, 1), ("3 Months", 56.25, 75.00, 3), ("6 Months", 99.98, 150.00, 6)]),
    ("BSOSOFT", "Black Seed Oil Softgels", "Herbal", False, LAUNCH_IMMUNITY, [
        ("1 Month", 30.00, 30.00, 1), ("3 Months", 50.00, 60.00, 3), ("6 Months", 90.00, 120.00, 6)]),
    ("PROBIOTIC", "Probiotic", "Gut Health", False, LAUNCH_PROBIOTIC, [
        ("1 Month", 30.00, 30.00, 1), ("3 Months", 45.00, 90.00, 3), ("6 Months", 80.00, 180.00, 6)]),
]


def _build_catalog() -> list[ProductSpec]:
    """Catalog grounded in products.json (2026-08-13) prices, options and published_at dates."""
    out: list[ProductSpec] = []
    add = out.append

    # --- Supplements: 1 / 3 / 6-month supply variants of one product ------------------
    for key, title, ptype, hero, launch, variants in _SUPPLEMENTS:
        for option, price, compare_at, months in variants:
            add(ProductSpec(
                sku=f"SUN-{key}-{months}M",
                title=title,
                option_1=option,
                product_key=key,
                product_type=ptype,
                role=f"supply_{months}m",
                base_price=price,
                compare_at_price=compare_at,
                subscription_eligible=True,
                sub_discount=SUB_DISCOUNT_HERO if hero else SUB_DISCOUNT_STANDARD,
                supply_months=months,
                current=True,
                launch_date=launch,
            ))

    # --- Single-variant bundles and one-offs -----------------------------------------
    add(ProductSpec("SUN-COLLAGEN-3M-750G", "Collagen 3 Month Supply (750g)", "3 Month Supply",
                    "COLLAGEN750", "Collagen", "supply_3m", 56.25, 75.00, True,
                    SUB_DISCOUNT_HERO, 3, True, "2024-11-29"))
    add(ProductSpec("SUN-ELECTRO-DUO", "Electrolytes - Tropical Refresh (Duo)", "Default Title",
                    "ELECTRODUO", "Hydration", "bundle", 60.00, 70.00, False,
                    0.0, 2, True, LAUNCH_DUO_BUNDLES))
    add(ProductSpec("SUN-CREATINE-DUO", "Creatine Monohydrate - Unflavoured (Duo)", "Default Title",
                    "CREATINEDUO", "Sports Nutrition", "bundle", 50.00, 50.00, False,
                    0.0, 2, True, LAUNCH_DUO_BUNDLES))
    add(ProductSpec("SUN-GUTHEALTH", "Gut Health Bundle", "Default Title",
                    "GUTHEALTH", "Gut Health", "bundle", 60.00, 80.00, False,
                    0.0, 1, True, "2025-07-15"))
    add(ProductSpec("SUN-SUHOOR", "Suhoor Support +", "Default Title",
                    "SUHOOR", "Ramadan", "bundle", 45.00, 45.00, False,
                    0.0, 1, True, "2025-04-07"))

    # --- Accessories -------------------------------------------------------------------
    for option, price, qty in [("1 Tumbler", 9.99, 1), ("3 Tumblers", 20.00, 3), ("6 Tumblers", 40.00, 6)]:
        add(ProductSpec(f"SUN-TUMBLER-{qty}", "Transparent Tumbler", option, "TUMBLER",
                        "Accessories", "accessory", price, price, False, 0.0, 0, True, "2024-10-31"))
    for colour in ["Blue", "Black"]:
        for option, price, qty in [("1 Shaker", 5.99, 1), ("3 Shakers", 15.00, 3), ("6 Shakers", 25.00, 6)]:
            add(ProductSpec(f"SUN-SHAKER-{colour.upper()}-{qty}", "Shaker Bottle",
                            f"{colour} / {option}", "SHAKER", "Accessories", "accessory",
                            price, price, False, 0.0, 0, True, "2023-11-23"))
    add(ProductSpec("SUN-MISWAK", "Miswak", "Default Title", "MISWAK",
                    "Accessories", "accessory", 4.99, 20.00, False, 0.0, 0, True, "2024-11-28"))

    # --- Genuine GBP 0.00 gift / lead-magnet SKUs (a selected data issue) -------------
    add(ProductSpec("SUN-GIFT-SHAKER", "BPA-Free Shaker Bottle", "Default Title", "GIFTSHAKER",
                    "Gift", "gift", 0.00, 9.95, False, 0.0, 0, True, "2025-10-16"))
    add(ProductSpec("SUN-GIFT-COLLAGENBP", "The Collagen Optimisation Blueprint", "Default Title",
                    "GIFTCOLBP", "Gift", "gift", 0.00, 19.95, False, 0.0, 0, True, "2025-10-16"))
    add(ProductSpec("SUN-GIFT-HYDRATIONBP", "The Hydration Optimisation Blueprint", "Default Title",
                    "GIFTHYDBP", "Gift", "gift", 0.00, 19.95, False, 0.0, 0, True, "2025-10-23"))

    # --- Navidium shipping protection ------------------------------------------------
    # The live store carries 100 price-ladder variants (NVDPROTECTION0..99). Modelled with a
    # reduced 12-tier ladder; this is a protected low-row dimension, not merchandise.
    for tier, price in enumerate(
        [0.99, 1.50, 2.25, 3.00, 3.75, 4.50, 5.25, 6.00, 6.75, 7.50, 8.25, 9.00], start=0
    ):
        add(ProductSpec(f"NVDPROTECTION{tier}", "Shipping Protection", f"{price}", "NVDPROTECTION",
                        "Shipping Protection", "shipping_protection", price, price,
                        False, 0.0, 0, True, "2024-11-28"))

    # --- Legacy / delisted, adjacent to the observed price architecture ---------------
    add(ProductSpec("SUN-COLLAGEN-SHAKER", "Halal Collagen Protein + Free Shaker", "Default Title",
                    "COLLAGENSHAKER", "Collagen", "supply_1m", 25.00, 25.00, True,
                    SUB_DISCOUNT_HERO, 1, False, "2025-06-26", "2025-10-31"))
    for option, price, qty in [("1 Shaker", 5.99, 1), ("3 Shakers", 15.00, 3)]:
        add(ProductSpec(f"SUN-SHAKER-RED-{qty}", "Shaker Bottle", f"Red / {option}", "SHAKER",
                        "Accessories", "accessory", price, price, False, 0.0, 0, False,
                        "2023-11-23", "2026-03-31"))
    add(ProductSpec("SUN-COLLAGEN-250G", "Halal Collagen Protein - Unflavoured 250g", "250g",
                    "COLLAGEN250", "Collagen", "supply_1m", 20.00, 20.00, True,
                    SUB_DISCOUNT_HERO, 1, False, "2024-01-15", "2025-06-30"))
    add(ProductSpec("SUN-RAMADAN-BUNDLE", "Ramadan Essentials Bundle", "Default Title",
                    "RAMADANBUNDLE", "Ramadan", "bundle", 55.00, 70.00, False,
                    0.0, 1, False, "2025-02-01", "2026-03-31"))
    add(ProductSpec("SUN-VITC-EFF", "Vitamin C Effervescent", "1 Tube", "VITC",
                    "Vitamins", "supply_1m", 15.00, 15.00, True,
                    SUB_DISCOUNT_STANDARD, 1, False, "2024-09-01", "2025-11-30"))
    add(ProductSpec("SUN-TOTE", "Sunna Tote Bag", "Default Title", "TOTE",
                    "Accessories", "accessory", 7.99, 7.99, False, 0.0, 0, False,
                    "2025-01-01", "2026-02-28"))
    return out


PRODUCTS: list[ProductSpec] = _build_catalog()


# Monthly order targets (promo- and seasonality-inclusive) from the approved trajectory.
# Islamic-calendar seasonality is BAKED IN here, not applied as a separate multiplier.
MONTHLY_ORDER_TARGETS = {
    "2025-03": 18200,
    "2025-04": 14400,
    "2025-05": 14900,
    "2025-06": 17100,
    "2025-07": 15400,
    "2025-08": 15800,
    "2025-09": 18500,
    "2025-10": 19600,
    "2025-11": 24700,
    "2025-12": 21000,
    "2026-01": 23900,
    "2026-02": 27400,
    "2026-03": 26500,
    "2026-04": 21900,
    "2026-05": 24500,
    "2026-06": 23500,
    "2026-07": 22500,
    "2026-08": 23300,
    "2026-09": 26800,
    "2026-10": 28000,
    "2026-11": 34700,
    "2026-12": 28800,
    "2027-01": 34100,
    "2027-02": 37400,
}

# Per-month target AOV (net of discount, VAT-inclusive, shipping-excluded). The basket
# controller in generate_raw steers mean(total_price) to this.
MONTHLY_AOV = {
    "2025-03": 39.54,
    "2025-04": 37.75,
    "2025-05": 38.84,
    "2025-06": 39.17,
    "2025-07": 39.49,
    "2025-08": 39.81,
    "2025-09": 40.13,
    "2025-10": 40.45,
    "2025-11": 38.53,
    "2025-12": 41.10,
    "2026-01": 41.42,
    "2026-02": 43.20,
    "2026-03": 43.32,
    "2026-04": 41.53,
    "2026-05": 42.70,
    "2026-06": 43.03,
    "2026-07": 43.35,
    "2026-08": 43.67,
    "2026-09": 43.99,
    "2026-10": 44.31,
    "2026-11": 42.18,
    "2026-12": 44.96,
    "2027-01": 46.64,
    "2027-02": 47.20,
}

# Refund rate: ~2.8% baseline for supplements with a 30-day money-back guarantee, higher in
# promo windows and in the month after Eid al-Fitr (bulk Ramadan buys come back).
MONTHLY_REFUND_RATE = {m: 0.028 for m in MONTHLY_ORDER_TARGETS}
for _m in ("2025-11", "2025-12", "2026-11", "2026-12"):
    MONTHLY_REFUND_RATE[_m] = 0.038
for _m in ("2025-04", "2026-04"):
    MONTHLY_REFUND_RATE[_m] = 0.040

_MONTH_KEYS = list(MONTHLY_ORDER_TARGETS)
_LAST = len(_MONTH_KEYS) - 1


def _ramp(start: float, end: float, month_key: str) -> float:
    return start + (end - start) * (_MONTH_KEYS.index(month_key) / _LAST)


def sub_take_rate(month_key: str) -> float:
    """Share of first orders that start a Skio subscription, ramping as Skio matures."""
    rate = _ramp(SUB_TAKE_RATE_START, SUB_TAKE_RATE_END, month_key)
    if month_key.endswith("-11"):
        rate *= SUB_TAKE_RATE_BLACK_FRIDAY_FACTOR
    return rate


def adhoc_repeat_share(month_key: str) -> float:
    return _ramp(ADHOC_REPEAT_SHARE_START, ADHOC_REPEAT_SHARE_END, month_key)


def supply_tier_weights(month_key: str) -> dict[int, float]:
    """Supply-tier mix (1 / 3 / 6-month), drifting toward bulk over the window and shifting
    hard toward bulk during Ramadan as customers stock up before fasting."""
    w1 = _ramp(0.72, 0.62, month_key)
    w3 = _ramp(0.22, 0.27, month_key)
    w6 = _ramp(0.06, 0.11, month_key)
    if month_key in RAMADAN_MONTHS:
        moved = min(w1 - 0.30, RAMADAN_BULK_SHIFT)
        w1 -= moved
        w3 += moved * 0.65
        w6 += moved * 0.35
    total = w1 + w3 + w6
    return {1: w1 / total, 3: w3 / total, 6: w6 / total}
