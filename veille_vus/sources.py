import hashlib, html, json, re, urllib.request, urllib.robotparser
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

UA = "veille-vus/0.1 (personal daily vehicle research)"

def text(el, names):
    for name in names:
        found = el.find(name)
        if found is not None and found.text: return html.unescape(found.text.strip())
    return ""

def infer(title, description=""):
    blob = html.unescape(re.sub(r"<[^>]+>", " ", title + " " + description))
    year_m = re.search(r"\b(20(?:1[6-9]|2[0-6]))\b", blob)
    price_m = re.search(r"(?:\$\s*([\d ,]{4,})|([\d ,]{4,})\s*\$)", blob)
    km_m = re.search(r"([\d ,]{2,})\s*(?:km|kilom)", blob, re.I)
    models = [("Mazda","CX-5"),("Honda","CR-V"),("Toyota","RAV4"),("Subaru","Forester"),
              ("Subaru","Outback"),("Toyota","Venza"),("Volkswagen","Tiguan")]
    make = model = None
    for a,b in models:
        if re.search(re.escape(b), blob, re.I): make,model=a,b; break
    def number(m): return int(re.sub(r"\D", "", next(g for g in m.groups() if g))) if m else None
    fuel = "Hybride" if re.search(r"hybrid|hybride", blob, re.I) else "Essence"
    drive = "AWD" if re.search(r"\b(?:AWD|TI|4x4)\b", blob, re.I) else None
    return dict(make=make, model=model, year=int(year_m.group()) if year_m else None,
                price=number(price_m), mileage=number(km_m), fuel=fuel, drivetrain=drive)

def collect_rss(source, timeout=20):
    req = urllib.request.Request(source["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        root = ET.fromstring(response.read())
    entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
    out = []
    for entry in entries:
        title = text(entry,["title","{http://www.w3.org/2005/Atom}title"])
        desc = text(entry,["description","summary","{http://www.w3.org/2005/Atom}summary"])
        url = text(entry,["link"])
        if not url:
            link = entry.find("{http://www.w3.org/2005/Atom}link")
            url = link.get("href", "") if link is not None else ""
        guid = text(entry,["guid","id","{http://www.w3.org/2005/Atom}id"]) or url
        if not url: continue
        item = {"source":source["name"], "external_id":hashlib.sha256(guid.encode()).hexdigest()[:24],
                "url":url, "title":title, "location":source.get("default_location"), "seller_type":None}
        item.update(infer(title, desc))
        out.append(item)
    return out

class JsonLdParser(HTMLParser):
    def __init__(self): super().__init__(); self.capture=False; self.parts=[]; self.blocks=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag.lower()=="script" and attrs.get("type","").lower()=="application/ld+json": self.capture=True; self.parts=[]
    def handle_data(self,data):
        if self.capture:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=="script" and self.capture:self.blocks.append("".join(self.parts));self.capture=False

def objects(value):
    if isinstance(value,list):
        for x in value: yield from objects(x)
    elif isinstance(value,dict):
        yield value
        if "@graph" in value: yield from objects(value["@graph"])

def _allowed(url, timeout):
    parts=urlparse(url); robots=f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp=urllib.robotparser.RobotFileParser(); rp.set_url(robots)
    req=urllib.request.Request(robots,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=timeout) as r: rp.parse(r.read().decode(errors="replace").splitlines())
    return rp.can_fetch(UA,url)

def collect_jsonld(source, timeout=25):
    urls=source.get("urls") or [source["url"]]; out=[]
    for page_url in urls:
        if not _allowed(page_url,timeout): raise PermissionError(f"robots.txt refuse {page_url}")
        req=urllib.request.Request(page_url,headers={"User-Agent":UA})
        with urllib.request.urlopen(req,timeout=timeout) as response: body=response.read(5_000_000).decode(errors="replace")
        parser=JsonLdParser(); parser.feed(body)
        for block in parser.blocks:
            try: values=list(objects(json.loads(block)))
            except json.JSONDecodeError: continue
            for obj in values:
                kinds=obj.get("@type",[]); kinds=[kinds] if isinstance(kinds,str) else kinds
                if "Vehicle" not in kinds: continue
                offer=obj.get("offers") or {}; seller=offer.get("seller") or {}; desc=obj.get("description") or ""
                rel=(obj.get("url") or "").replace("auto-usage/auto-usage/","auto-usage/")
                if rel and not rel.startswith(("/","http://","https://")): rel="/"+rel
                url=urljoin(page_url,rel); vin=obj.get("vehicleIdentificationNumber")
                ext=vin or hashlib.sha256(url.encode()).hexdigest()[:24]
                model=obj.get("model"); brand=obj.get("brand"); brand=brand.get("name") if isinstance(brand,dict) else brand
                carfax=1 if re.search(r"carfax",desc,re.I) else None
                accident="Aucun accident déclaré" if re.search(r"jamais accident|aucun accident",desc,re.I) else None
                owners=1 if re.search(r"(?:1|un)\s*(?:seul\s*)?propri",desc,re.I) else None
                out.append({"source":source["name"],"external_id":ext,"url":url,"title":obj.get("name"),
                  "make":brand,"model":model,"trim":obj.get("vehicleConfiguration"),
                  "year":obj.get("vehicleModelDate"),"price":offer.get("price"),
                  "mileage":obj.get("mileageFromOdometer"),"location":source.get("default_location"),
                  "seller_type":"Concessionnaire","seller_name":seller.get("name"),
                  "fuel":obj.get("fuelType"),"accident_history":accident,"owners":owners,"carfax":carfax})
    return list({(x["source"],x["external_id"]):x for x in out}.values())
