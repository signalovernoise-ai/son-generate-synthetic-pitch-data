"""Constants, catalog and monthly target series for Fussy.

Grounded in the live getfussy.com Shopify storefront (products.json, 2026-08-06) and the
approved trajectory in
skills/company-synthetic-data-workflow/assets/company-setups/fussy.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass


BUSINESS = "fussy"
SEED = 20260806
# Full-scale build (~2.03m orders -> ~14.5m rows) far exceeds the 5m gate. The 18-month
# historic window is kept because the 3-monthly refill cadence needs the depth; operational
# row volume is scaled instead. Rates are scale-invariant; products are never scaled.
ROW_SCALE = 0.20

# Default modeling window: 18 historic + 6 future months (today 2026-08-06).
SOURCE_WINDOW_START = "2025-03-01"
SOURCE_WINDOW_END = "2027-02-28"

# Source-specific windows.
KLAVIYO_START = "2025-09-01"        # email/SMS stream trimmed to the last 12 historic months
GOOGLE_ADS_START = "2025-03-01"     # full window

# Evidenced range launches (products.json published_at).
BODY_WASH_LAUNCH = "2025-08-20"
HAND_WASH_LAUNCH = "2025-11-20"
HAND_WASH_REFILL_LAUNCH = "2025-12-11"
LIMITED_EDITION_LAUNCH = "2026-05-18"

# Channel-tracking break windows (consent / tag-manager changes).
TRACKING_BREAKS = [
    ("2025-11-24", 8, 0.22),   # Cyber Week tagging change
    ("2026-04-13", 7, 0.20),   # consent-mode / Littledata reconfiguration
]
UNATTRIBUTED_BASELINE = 0.08

# UK VAT is standard-rated on personal care; prices on site are VAT-inclusive.
VAT_RATE = 0.20

# Delivery: flat fee, no spend threshold (so no basket bunching to model).
SHIPPING_SUBSCRIPTION = 1.00   # refill-only recurring deliveries
SHIPPING_STANDARD = 1.99       # everything else
SHIPPING_FIRST_SUB = 0.00      # free on the initial Subscribe & Save starter

# Subscribe & Save: refills drop from £6.00 to ~£5.00 each (£15.00 per 3-refill delivery).
SUBSCRIPTION_DISCOUNT = 0.1667
SUB_TAKE_RATE = 0.50           # share of first orders that start a subscription
SUB_TAKE_RATE_BLACK_FRIDAY = 0.42  # discount-led November cohorts convert worse
ADHOC_REPEAT_SHARE = 0.16      # share of monthly orders that are one-time repeat purchases
MIN_NEW_SHARE = 0.24           # floor share of monthly orders that are new acquisitions

# Renewal survival by cycle index (1 = first refill delivery a month after the starter,
# then every 3 months). Calibrated so renewal *demand* matches the renewal *capacity* the
# monthly order targets leave free (~3.3 renewals per subscriber at a 0.50 take-rate and a
# 0.32 new-customer share). Chronic over-demand would force constant skipping, which smears
# the cadence and flattens the retention sawtooth.
RENEWAL_SURVIVAL = {1: 0.86, 2: 0.80, 3: 0.78, 4: 0.70}
RENEWAL_SURVIVAL_TAIL = 0.70

# Data-issue prevalences (see fussy.yaml data_issues).
EMAIL_DRIFT_RATE = 0.022
DUPLICATE_ORDER_NAME_RATE = 0.004
TEST_ORDER_RATE = 0.0022
GA4_RENEWAL_CAPTURE = 0.08     # share of renewals that still reach GA4 (Direct / not set only)
GA4_WEB_LOSS = 0.07            # tag/consent loss on genuine web checkouts
CANCEL_LAG_RATE = 0.15         # share of cancels recorded well after the last charge
GORGIAS_NO_ORDER_RATE = 0.35
GORGIAS_NO_CUSTOMER_RATE = 0.08


@dataclass(frozen=True)
class ProductSpec:
    sku: str
    title: str
    product_type: str
    role: str              # drives basket construction
    base_price: float
    compare_at_price: float
    subscription_eligible: bool
    current: bool
    launch_date: str
    retire_date: str | None = None


_CORE_SCENTS = [
    "Wavy Days", "Tropic Tonic", "Coconut Milk", "Lavender Fields",
    "Wilderness", "Road Trip", "All at Sea", "Wide Eyed",
]
_LE_SCENTS = ["Mango Mood", "Sweet Escape", "After Sun"]
_CASE_COLOURS = ["Ocean Blue", "Mint Green", "Blush", "Midnight", "Orange", "Lilac"]


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("&", "and")


def _build_catalog() -> list[ProductSpec]:
    """Catalog grounded in products.json (2026-08-06) prices and published_at dates."""
    out: list[ProductSpec] = []
    add = out.append

    # --- Deodorant: starter packs (case + 1 refill), £15 core / £17 limited edition ----
    for scent in _CORE_SCENTS:
        add(ProductSpec(
            f"FUS-DEO-START-{_slug(scent).upper()}", f"{scent} Starter Pack",
            "Deodorant & Anti-Perspirant", "starter", 15.00, 16.00, True, True, "2025-01-10",
        ))
    for scent in ["Sugar Crush", "Forest Haze", "Cloud Nine"]:
        add(ProductSpec(
            f"FUS-DEO-START-SENS-{_slug(scent).upper()}", f"{scent} Sensitive Starter Pack",
            "Deodorant & Anti-Perspirant", "starter", 15.00, 16.00, True, True, "2025-01-10",
        ))
    for scent in _LE_SCENTS:
        add(ProductSpec(
            f"FUS-DEO-START-LE-{_slug(scent).upper()}", f"{scent} Starter Pack",
            "Deodorant & Anti-Perspirant", "starter_le", 17.00, 19.00, True, True,
            LIMITED_EDITION_LAUNCH,
        ))
    add(ProductSpec(
        "FUS-DEO-START-LE-LOSTCLAUS", "Lost Claus Starter Pack",
        "Deodorant & Anti-Perspirant", "starter_le", 17.00, 19.00, True, False,
        "2025-10-15", "2026-01-31",
    ))

    # --- Deodorant: refill packs (3 refills) £18, singles £6 --------------------------
    for name in ["Fresh", "Variety", "Most Loved Scents", "Fresh & Floral", "Day & Night"]:
        add(ProductSpec(
            f"FUS-DEO-RP-{_slug(name).upper()}", f"{name} Refill Pack",
            "Refills", "refill_pack", 18.00, 18.00, True, True, "2025-01-10",
        ))
    for scent in _LE_SCENTS:
        add(ProductSpec(
            f"FUS-DEO-RP-LE-{_slug(scent).upper()}", f"{scent} Refill Pack",
            "Refills", "refill_pack", 18.00, 18.00, True, True, LIMITED_EDITION_LAUNCH,
        ))
    add(ProductSpec("FUS-DEO-REFILL", "Refills", "Refills", "refill_single",
                    6.00, 6.00, True, True, "2025-01-10"))
    add(ProductSpec("FUS-DEO-REFILL-SENS", "Sensitive Refills", "Refills", "refill_single",
                    6.00, 6.00, True, True, "2025-01-10"))

    # --- Deodorant: scent packs (case + 3 refills) £30 / £28 limited edition ----------
    for scent in ["All at Sea", "Coconut Milk", "Wavy Days", "Tropic Tonic"]:
        add(ProductSpec(
            f"FUS-DEO-SP-{_slug(scent).upper()}", f"{scent} Scent Pack",
            "Deodorant & Anti-Perspirant", "scent_pack", 30.00, 33.00, True, True, "2025-01-10",
        ))
    for scent in _LE_SCENTS[:2]:
        add(ProductSpec(
            f"FUS-DEO-SP-LE-{_slug(scent).upper()}", f"{scent} Scent Pack",
            "Deodorant & Anti-Perspirant", "scent_pack", 28.00, 31.00, True, True,
            LIMITED_EDITION_LAUNCH,
        ))

    # --- Minis £10 --------------------------------------------------------------------
    for name in ["Lavender Fields", "Night Tales", "Sun Drunk", "Birthday Cake",
                 "Sugar Crush", "Wavy Days"]:
        add(ProductSpec(
            f"FUS-DEO-MINI-{_slug(name).upper()}", f"{name} Mini Trio Pack",
            "Add ons", "mini", 10.00, 10.00, False, True, "2025-01-10",
        ))

    # --- Cases £10 (legacy Outer Case £8) --------------------------------------------
    for colour in _CASE_COLOURS:
        add(ProductSpec(
            f"FUS-CASE-{_slug(colour).upper()}", f"{colour} Case", "Case", "case",
            10.00, 10.00, False, True, "2025-01-10",
        ))
    add(ProductSpec("FUS-CASE-OUTER", "Outer Case", "Case", "case",
                    8.00, 8.00, False, False, "2025-01-10", "2025-09-30"))

    # --- Body wash (range live 2025-08-20) -------------------------------------------
    for scent in ["Coconut Milk", "All at Sea", "Wide Eyed"]:
        add(ProductSpec(
            f"FUS-BW-START-{_slug(scent).upper()}", f"{scent} Body Wash Starter Pack",
            "Body Wash", "bw_starter", 19.00, 21.00, True, True, BODY_WASH_LAUNCH,
        ))
        add(ProductSpec(
            f"FUS-BW-RP-{_slug(scent).upper()}", f"{scent} Body Wash Refill Pack",
            "Body Wash Refills", "bw_refill", 21.00, 21.00, True, True, BODY_WASH_LAUNCH,
        ))
    add(ProductSpec("FUS-BW-REFILL", "Body Wash Refill", "Body Wash Refills", "bw_refill_single",
                    7.00, 7.00, True, True, BODY_WASH_LAUNCH))
    for colour in ["Stone Grey", "Mint Green", "Lilac"]:
        add(ProductSpec(
            f"FUS-BW-BOTTLE-{_slug(colour).upper()}", f"{colour} Body Wash Bottle",
            "Bottle", "bottle", 12.00, 12.00, False, True, BODY_WASH_LAUNCH,
        ))
    for name in ["Natural Body Bar Pack", "Exfoliating Body Bar Pack"]:
        add(ProductSpec(
            f"FUS-BAR-{_slug(name).upper()}", name, "Add ons", "bodybar",
            12.00, 12.00, False, True, "2025-01-10",
        ))

    # --- Hand wash (bottles live 2025-11-20, refills 2025-12-11) ---------------------
    for scent in ["Coconut Milk", "Wide Eyed"]:
        add(ProductSpec(
            f"FUS-HW-START-{_slug(scent).upper()}", f"{scent} Hand Wash Starter Pack",
            "Hand Wash", "hw_starter", 15.00, 16.00, True, True, HAND_WASH_LAUNCH,
        ))
    for colour in ["Stone Grey", "Mint Green", "Orange", "Lilac"]:
        add(ProductSpec(
            f"FUS-HW-BOTTLE-{_slug(colour).upper()}", f"{colour} Hand Wash Bottle",
            "Bottle", "bottle", 10.00, 10.00, False, True, HAND_WASH_LAUNCH,
        ))
    for name in ["Hand Wash Variety", "Hand Wash Tropical", "Hand Wash Fresh"]:
        add(ProductSpec(
            f"FUS-HW-RP-{_slug(name).upper()}", f"{name} Refill Pack",
            "Hand Wash Refills", "hw_refill", 18.00, 18.00, True, True, HAND_WASH_REFILL_LAUNCH,
        ))
    add(ProductSpec("FUS-HW-REFILL", "Hand Wash Refills", "Hand Wash Refills",
                    "hw_refill_single", 6.00, 6.00, True, True, HAND_WASH_REFILL_LAUNCH))

    # --- Accessories and gift cards ---------------------------------------------------
    add(ProductSpec("FUS-ACC-WASHBAG", "Recycled Washbag", "Add ons", "accessory",
                    10.00, 10.00, False, False, "2025-01-10", "2026-06-30"))
    for value in (5, 10, 15, 20):
        add(ProductSpec(
            f"FUS-GIFT-{value}", f"Fussy Gift Card - £{value}", "Gift Cards", "giftcard",
            float(value), float(value), False, True, "2025-01-10",
        ))
    return out


PRODUCTS: list[ProductSpec] = _build_catalog()


# Monthly order targets (promo- and seasonality-inclusive) from the approved trajectory.
MONTHLY_ORDER_TARGETS = {
    "2025-03": 67000,
    "2025-04": 69800,
    "2025-05": 74700,
    "2025-06": 78300,
    "2025-07": 80500,
    "2025-08": 75400,
    "2025-09": 72800,
    "2025-10": 75800,
    "2025-11": 89700,
    "2025-12": 84000,
    "2026-01": 87300,
    "2026-02": 76700,
    "2026-03": 79900,
    "2026-04": 83200,
    "2026-05": 89100,
    "2026-06": 95200,
    "2026-07": 97900,
    "2026-08": 91800,
    "2026-09": 85500,
    "2026-10": 89100,
    "2026-11": 105400,
    "2026-12": 96300,
    "2027-01": 100100,
    "2027-02": 88000,
}

# Per-month target AOV (net of discount, VAT-inclusive, shipping-excluded). The basket
# controller in generate_raw steers mean(total_price) to this.
MONTHLY_AOV = {
    "2025-03": 16.80,
    "2025-04": 16.86,
    "2025-05": 17.16,
    "2025-06": 17.22,
    "2025-07": 17.28,
    "2025-08": 17.07,
    "2025-09": 17.48,
    "2025-10": 17.54,
    "2025-11": 16.80,
    "2025-12": 17.63,
    "2026-01": 17.95,
    "2026-02": 18.01,
    "2026-03": 18.06,
    "2026-04": 18.12,
    "2026-05": 18.44,
    "2026-06": 18.70,
    "2026-07": 18.76,
    "2026-08": 18.54,
    "2026-09": 18.59,
    "2026-10": 18.64,
    "2026-11": 17.86,
    "2026-12": 18.47,
    "2027-01": 18.81,
    "2027-02": 18.87,
}

# Refund rate: ~2.0% baseline for low-value personal care, higher after promo windows.
MONTHLY_REFUND_RATE = {m: 0.020 for m in MONTHLY_ORDER_TARGETS}
for _m in ("2025-11", "2025-12", "2026-06", "2026-11", "2026-12"):
    MONTHLY_REFUND_RATE[_m] = 0.026

# Cross-sell rate onto an existing subscription (a second subscribed line: body wash or
# hand wash refills). Zero before the body wash range launches.
MONTHLY_SUB_CROSSSELL = {}
for _i, _m in enumerate(MONTHLY_ORDER_TARGETS):
    if _m < "2025-09":
        MONTHLY_SUB_CROSSSELL[_m] = 0.0
    else:
        MONTHLY_SUB_CROSSSELL[_m] = min(0.16, 0.05 + 0.007 * (_i - 5))
