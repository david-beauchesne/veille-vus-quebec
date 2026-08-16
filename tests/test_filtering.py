import tomllib
import unittest

def wanted_models(cfg):
    names=cfg["search"]["primary_models"]+cfg["search"]["secondary_models"]
    return {name.lower().removesuffix(" hybrid") for name in names}

class FilteringTests(unittest.TestCase):
    def test_hybrid_names_match_base_listing_model(self):
        with open("config.toml","rb") as f: cfg=tomllib.load(f)
        wanted=wanted_models(cfg)
        self.assertIn("toyota rav4",wanted)
        self.assertIn("toyota venza",wanted)
        self.assertIn("mazda cx-30",wanted)
        self.assertIn("toyota corolla cross",wanted)
        self.assertNotIn("subaru crosstrek",wanted)
