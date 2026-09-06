# Seasonality Calendars

Most D2C seasonality is Gregorian: Black Friday, January, summer. Some brands' peak trading
windows run on a **different calendar**, and when they do it is usually the single most
important thing about their demand curve — and the easiest to model wrongly.

## When this applies

Check for it whenever the brand's audience is defined by faith, culture or region rather than
by category alone: halal/Muslim-focused brands (Ramadan, Eid al-Fitr, Eid al-Adha), East and
Southeast Asian brands (Lunar New Year), South Asian brands (Diwali), Jewish brands (Passover,
Rosh Hashanah). Product names are the giveaway — a SKU named for a religious observance
(e.g. a "Suhoor" or "Iftar" product) is direct evidence the brand trades that calendar
deliberately.

## The modelling rule: the peak migrates

The Islamic (Hijri) calendar is lunar and runs ~11 days shorter than the Gregorian year, so
**every Islamic date moves ~11 days earlier each Gregorian year**. Over a 24-month window the
peak walks across month boundaries:

| Observance | 2025 | 2026 | 2027 |
|---|---|---|---|
| Ramadan begins | 1 Mar | 18 Feb | 8 Feb |
| Eid al-Fitr | 30 Mar | 20 Mar | 10 Mar |
| Eid al-Adha | 6 Jun | 27 May | 17 May |

Lunar New Year moves within Jan–Feb; Diwali within Oct–Nov. Confirm actual dates rather than
assuming — observance start dates are moon-sighting dependent and vary by a day between
regions.

Consequences to model explicitly:

- **Put the peak in the right month, per year.** Do not apply one fixed monthly multiplier
  across the window; the multiplier has to move with the calendar.
- **Year-on-year month comparison breaks.** March 2026 against March 2025 compares a
  full-Ramadan month against a partial one and reads as a decline in a business that grew.
  State this in the setup artifact as an analytical trap — it is usually the most interesting
  finding the dataset can carry.
- **Comparisons must be observance-aligned**, not month-aligned. The correct read is
  Ramadan-over-Ramadan.

## Second-order effects worth modelling

- **Basket mix shifts, not just volume.** Stock-up occasions skew hard toward multi-month /
  bulk variants. Model this as a real shift in the supply-tier mix, which raises AOV in the
  peak month.
- **Bulk buying suppresses near-term repeat.** A customer who buys a 3- or 6-month supply is
  genuinely not in the market for months. Implement it as an eligibility delay in the repeat
  pool, never as a label. The result — the brand's largest acquisition cohorts scoring worst
  on an order-recency retention curve — is an artefact of basket size, not customer quality,
  and is a strong pitch insight.
- **The trough follows the peak.** Expect a sharp drop in the month after the observance ends,
  and a refund-rate bump as bulk purchases come back.

## Recording it

Put the observance dates in the company `config.py` as explicit constants, list the affected
months in the setup artifact's `seasonality_notes`, and bake the shape into the monthly order
path rather than applying a separate multiplier layer (see `metric-definitions.md`).
