import tempfile
import unittest
from pathlib import Path
from veille_vus.db import connect, upsert
class DatabaseTests(unittest.TestCase):
    def test_deduplicates_and_tracks_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            con=connect(Path(directory)/"v.db"); item={"source":"x","external_id":"1","url":"https://x/1","price":25000}
            _,new1=upsert(con,item,"2026-01-01T00:00:00+00:00"); item["price"]=24000
            _,new2=upsert(con,item,"2026-01-02T00:00:00+00:00")
            self.assertTrue(new1 and not new2)
            self.assertEqual(con.execute("select count(*) from listings").fetchone()[0],1)
            self.assertEqual(con.execute("select count(*) from price_history").fetchone()[0],2)
