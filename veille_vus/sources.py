import hashlib, html, json, re, time, urllib.request, urllib.robotparser
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

UA = "veille-vus/0.1 (personal daily vehicle research)"
_ROBOTS_CACHE = {}
_LAST_FETCH = {}

def text(el, names):
    for name in names:
        found = el.find(name)
        if found is not None and found.text: return html.unescape(found.text.strip())
    return ""

def infer(title, description=""):
    blob = html.unescape(re.sub(r"<[^>]+>", " ", title + " " + description))
    year_m = re.search(r"\b(20(?:1[6-9]|2[0-6]))\b", blob)
    price_m = re.search(r"(?:\$\s*([\d ,]{4,})|([\d ,]{4,})\s*\$)", blob)
    km_m = re.search(r"(\d{1,3}(?:[ \u00a0,]\d{3})+|\d{2,6})\s*km\b", blob, re.I)
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
                "url":url, "title":title, "location":source.get("default_location"), "seller_type":None,
                "verification_status":"unverified", "data_confidence":0.35,
                "field_provenance":json.dumps({"url":"rss","title":"rss"})}
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
    if robots in _ROBOTS_CACHE: return _ROBOTS_CACHE[robots].can_fetch(UA,url)
    rp=urllib.robotparser.RobotFileParser(); rp.set_url(robots)
    req=urllib.request.Request(robots,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=timeout) as r: rp.parse(r.read().decode(errors="replace").splitlines())
    _ROBOTS_CACHE[robots]=rp
    return rp.can_fetch(UA,url)

def _download(url, timeout, delay=0):
    host=urlparse(url).netloc; elapsed=time.monotonic()-_LAST_FETCH.get(host,0)
    if delay and elapsed < delay: time.sleep(delay-elapsed)
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=timeout) as response: body=response.read(5_000_000).decode(errors="replace")
    _LAST_FETCH[host]=time.monotonic()
    return body

def _number(value):
    if isinstance(value,dict): value=value.get("value")
    if value in (None,""): return None
    try: return int(float(str(value).replace(" ","").replace(",","")))
    except ValueError: return None

def _vehicle_item(obj, page_url, source):
    offer=obj.get("offers") or {}; seller=offer.get("seller") or {}; desc=obj.get("description") or ""
    guessed=infer(obj.get("name") or "",desc)
    rel=(obj.get("url") or offer.get("url") or "").replace("auto-usage/auto-usage/","auto-usage/")
    if rel and not rel.startswith(("/","http://","https://")): rel="/"+rel
    url=urljoin(page_url,rel); vin=obj.get("vehicleIdentificationNumber")
    brand=obj.get("brand"); brand=brand.get("name") if isinstance(brand,dict) else brand
    model=obj.get("model") or guessed.get("model")
    mileage=_number(obj.get("mileageFromOdometer")); year=_number(obj.get("vehicleModelDate")) or guessed.get("year")
    price=_number(offer.get("price"))
    provenance={k:"schema.org Vehicle" for k,v in {"url":url,"make":brand,"model":model,"year":year,
      "price":price,"mileage":mileage}.items() if v is not None and v != ""}
    critical=all((url,brand,model,year,price,mileage is not None))
    drive=obj.get("driveWheelConfiguration")
    if isinstance(drive,str) and drive.startswith("http"): drive=drive.rsplit("/",1)[-1].replace("Configuration","")
    return {"source":source["name"],"external_id":vin or hashlib.sha256(url.encode()).hexdigest()[:24],
      "url":url,"title":obj.get("name"),"make":brand,"model":model,"trim":obj.get("vehicleConfiguration"),
      "year":year,"price":price,"mileage":mileage,"location":source.get("default_location"),
      "seller_type":"Concessionnaire","seller_name":seller.get("name") or source.get("seller_name"),
      "transmission":obj.get("vehicleTransmission"),"drivetrain":drive,"fuel":obj.get("fuelType"),
      "accident_history":"Aucun accident déclaré" if re.search(r"jamais accident|aucun accident",desc,re.I) else None,
      "owners":1 if re.search(r"(?:1|un)\s*(?:seul\s*)?propri",desc,re.I) else None,
      "carfax":1 if re.search(r"carfax",desc,re.I) else None,
      "verification_status":"verified" if critical else "discovered",
      "data_confidence":1.0 if critical else 0.45,"field_provenance":json.dumps(provenance,ensure_ascii=False)}

def _parse_vehicles(body, page_url, source):
    parser=JsonLdParser(); parser.feed(body); out=[]
    for block in parser.blocks:
        try: values=objects(json.loads(block))
        except json.JSONDecodeError: continue
        for obj in values:
            kinds=obj.get("@type",[]); kinds=[kinds] if isinstance(kinds,str) else kinds
            if "Vehicle" in kinds: out.append(_vehicle_item(obj,page_url,source))
    return out

def collect_jsonld(source, timeout=25):
    urls=source.get("urls") or [source["url"]]; out=[]
    for page_url in urls:
        if not _allowed(page_url,timeout): raise PermissionError(f"robots.txt refuse {page_url}")
        body=_download(page_url,timeout,float(source.get("detail_delay_seconds",0)))
        out.extend(_parse_vehicles(body,page_url,source))
    return list({(x["source"],x["external_id"]):x for x in out}.values())

def verify_detail(item, source, timeout=25):
    """Verify critical fields from the vehicle's own detail page; fail closed."""
    url=item.get("url")
    try:
        if not url or not _allowed(url,timeout): raise PermissionError("fiche refusée par robots.txt")
        body=_download(url,timeout,float(source.get("detail_delay_seconds",0)))
        candidates=_parse_vehicles(body,url,source)
        exact=[x for x in candidates if x.get("external_id")==item.get("external_id")]
        if not exact: raise ValueError("VIN absent ou différent sur la fiche")
        verified=exact[0]
        if verified["verification_status"] != "verified": raise ValueError("champs critiques incomplets sur la fiche")
        verified["verified_at"]=None
        return verified
    except Exception as exc:
        failed=dict(item); failed.update({"verification_status":"unverified","data_confidence":0.0,
          "verification_error":str(exc),"mileage":None,"fuel":None,"drivetrain":None,"transmission":None})
        return failed
