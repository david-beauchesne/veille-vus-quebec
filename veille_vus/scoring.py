def clamp(value, low=0.0, high=10.0):
    return max(low, min(high, value))

def linear(value, best, worst):
    if value is None: return 5.0
    return clamp(10 * (worst - value) / (worst - best))

def model_profile(item, cfg):
    name = f"{item.get('make','')} {item.get('model','')}".strip()
    fuel = (item.get("fuel") or "").lower()
    if name == "Toyota RAV4" and "hybrid" in fuel:
        name = "Toyota RAV4 Hybrid"
    return name, cfg.get("models", {}).get(name, {})

def weighted(values, weights):
    total = sum(weights.values()) or 1
    return round(sum(values.get(k, 5) * w for k, w in weights.items()) / total, 1)

def score(item, cfg, today_year=2026):
    name, p = model_profile(item, cfg)
    price = linear(item.get("price"), 20000, 32000)
    mileage = linear(item.get("mileage"), 35000, 130000)
    age = linear(today_year - item.get("year", today_year - 5), 2, 9)
    lt = weighted({
      "reliability":p.get("reliability",5), "mechanical_simplicity":p.get("simplicity",5),
      "maintenance_cost":p.get("maintenance",5), "fuel_economy":p.get("fuel",5),
      "mileage":mileage, "age":age, "price":price, "longevity":p.get("longevity",5)
    }, cfg["weights"]["long_term"])
    fs = weighted({
      "purchase_price":price, "residual_value":p.get("residual",5), "fuel_economy":p.get("fuel",5),
      "mileage":mileage, "resale_ease":p.get("resale",5), "reputation":p.get("reputation",5),
      "used_demand":p.get("demand",5)
    }, cfg["weights"]["four_six_year"])
    ow = cfg["weights"]["overall"]
    overall = round(lt*ow["long_term"] + fs*ow["four_six_year"] + p.get("driving",5)*ow["driving"], 1)
    return lt, fs, overall, recommendation(overall, item)

def recommendation(s, item):
    if item.get("status") == "disappeared": return "Disparu"
    if s >= 8.3: return "À contacter"
    if s >= 7.5: return "Bonne valeur"
    if s >= 6.4: return "À surveiller"
    return "Ignorer"

