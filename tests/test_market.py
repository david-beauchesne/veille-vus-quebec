import tempfile
import unittest
from pathlib import Path

from veille_vus.db import connect, upsert
from veille_vus.market import calculate, trim_value


class MarketTests(unittest.TestCase):
    def test_adjusts_comparables_and_rewards_discount(self):
        cfg = {"market": {"minimum_comparables": 2, "year_adjustment": 2000,
               "mileage_adjustment_per_10000_km": 1000,
               "discount_pct_per_score_point": 2, "trim_adjustments": {"GS": 1000}}}
        with tempfile.TemporaryDirectory() as directory:
            con = connect(Path(directory) / "v.db")
            base = {"source": "x", "make": "Mazda", "model": "CX-5", "year": 2022,
                    "mileage": 60000, "trim": "GS AWD", "verification_status": "verified"}
            for external_id, price, km in (("a", 25000, 50000), ("b", 23000, 70000),
                                            ("deal", 21000, 60000)):
                upsert(con, {**base, "external_id": external_id, "url": f"https://x/{external_id}",
                            "price": price, "mileage": km}, "2026-01-01T00:00:00+00:00")
            calculate(con, cfg)
            deal = con.execute("SELECT * FROM listings WHERE external_id='deal'").fetchone()
            self.assertEqual(deal["market_price"], 24000)
            self.assertLess(deal["market_delta_pct"], 0)
            self.assertGreater(deal["market_score"], 5)

    def test_trim_matching(self):
        self.assertEqual(trim_value("GS Comfort TI", {"GS": 1500}), 1500)
