import tomllib
import unittest
from veille_vus.scoring import score

def cfg():
    with open("config.toml","rb") as f:return tomllib.load(f)
class ScoringTests(unittest.TestCase):
    def test_better_price_and_mileage_score_higher(self):
        a={"make":"Toyota","model":"RAV4","year":2022,"price":23000,"mileage":60000,"fuel":"Essence","status":"active"}
        b={**a,"price":30000,"mileage":108000}
        self.assertGreater(score(a,cfg())[2], score(b,cfg())[2])
    def test_two_distinct_scores_and_label(self):
        x={"make":"Mazda","model":"CX-5","year":2021,"price":24000,"mileage":70000,"fuel":"Essence","status":"active"}
        lt,fs,total,label=score(x,cfg())
        self.assertTrue(0<=lt<=10 and 0<=fs<=10 and 0<=total<=10)
        self.assertIn(label,{"À contacter","Bonne valeur","À surveiller","Ignorer"})
