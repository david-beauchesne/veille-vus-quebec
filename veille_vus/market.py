import re
from statistics import median

from .scoring import clamp


def trim_value(trim, adjustments):
    """Return a conservative equipment adjustment from a free-form trim name."""
    name = (trim or "").lower()
    for key in ("Signature", "Turbo", "GT", "Kuro", "GS", "GX"):
        if re.search(rf"\b{key.lower()}\b", name):
            return adjustments.get(key, 0)
    return 0


def calculate(con, cfg):
    """Estimate asking-market value for each verified CX-5 from observed comparables."""
    settings = cfg.get("market", {})
    year_step = settings.get("year_adjustment", 2300)
    km_step = settings.get("mileage_adjustment_per_10000_km", 850)
    min_comps = settings.get("minimum_comparables", 5)
    pct_step = settings.get("discount_pct_per_score_point", 2.0)
    trims = settings.get("trim_adjustments", {})
    rows = [dict(r) for r in con.execute("""SELECT * FROM listings
        WHERE lower(make)='mazda' AND replace(lower(model),' ','') IN ('cx-5','cx5')
        AND verification_status='verified' AND price IS NOT NULL
        AND mileage IS NOT NULL AND year IS NOT NULL""")]

    for target in rows:
        same_year = [r for r in rows if r["id"] != target["id"] and r["year"] == target["year"]]
        pool = same_year if len(same_year) >= min_comps else [
            r for r in rows if r["id"] != target["id"] and abs(r["year"] - target["year"]) <= 1
        ]
        if len(pool) < min_comps:
            values = (None, None, None, None, len(pool), target["id"])
        else:
            target_trim = trim_value(target.get("trim"), trims)
            adjusted = []
            for comp in pool:
                estimate = comp["price"]
                estimate += (target["year"] - comp["year"]) * year_step
                estimate -= (target["mileage"] - comp["mileage"]) / 10000 * km_step
                estimate += target_trim - trim_value(comp.get("trim"), trims)
                adjusted.append(estimate)
            market_price = round(median(adjusted) / 100) * 100
            delta = target["price"] - market_price
            delta_pct = round(100 * delta / market_price, 1)
            market_score = round(clamp(5 - delta_pct / pct_step), 1)
            values = (market_price, delta, delta_pct, market_score, len(pool), target["id"])
        con.execute("""UPDATE listings SET market_price=?,market_delta=?,market_delta_pct=?,
            market_score=?,comparable_count=? WHERE id=?""", values)
