import unittest
from veille_vus.sources import infer, JsonLdParser, objects
import json
class SourceTests(unittest.TestCase):
    def test_infer_french_listing(self):
        x=infer("2021 Mazda CX-5 AWD - 24 900 $ - 68 000 km")
        self.assertEqual((x["make"],x["model"],x["year"],x["price"],x["mileage"]),("Mazda","CX-5",2021,24900,68000))
    def test_reads_jsonld_block(self):
        parser=JsonLdParser(); parser.feed('<script type="application/ld+json">{"@type":"Vehicle","model":"RAV4"}</script>')
        found=[x for b in parser.blocks for x in objects(json.loads(b)) if x.get("@type")=="Vehicle"]
        self.assertEqual(found[0]["model"],"RAV4")
    def test_infers_d2c_vehicle_name(self):
        x=infer("Mazda CX-5 2023", "Kilométrage 68 400 km")
        self.assertEqual((x["make"],x["model"],x["year"],x["mileage"]),("Mazda","CX-5",2023,68400))
