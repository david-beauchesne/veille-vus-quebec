import argparse, hashlib, json, re, tomllib, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from . import db
from .dashboard import build
from .scoring import score
from .sources import collect_rss, collect_jsonld, infer, UA

def config(path):
    with open(path,"rb") as f: return tomllib.load(f)
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def run_collect(cfg):
    con=db.connect(cfg["app"]["database"]); stamp=now(); new=seen=0
    for source in cfg.get("sources",[]):
        if not source.get("enabled",True): continue
        try:
            items = collect_rss(source) if source["type"] == "rss" else collect_jsonld(source)
        except Exception as e:
            print(f"AVERTISSEMENT {source['name']}: {e}"); continue
        for item in items:
            if item.get("year") and not cfg["search"]["min_year"] <= int(item["year"]) <= cfg["search"]["max_year"]: continue
            if item.get("price") and int(item["price"]) > cfg["search"]["absolute_price_max"]: continue
            if item.get("mileage") and int(item["mileage"]) > cfg["search"]["acceptable_mileage_max"]: continue
            _, created=db.upsert(con,item,stamp); new+=created; seen+=1
    cutoff=(datetime.now(timezone.utc)-timedelta(days=cfg["app"]["disappeared_after_days"])).isoformat()
    con.execute("UPDATE listings SET status='disappeared',recommendation='Disparu' WHERE status='active' AND last_seen<?",(cutoff,))
    rescore(con,cfg); con.commit(); print(f"{seen} annonces vues, {new} nouvelles")

def add_url(cfg,url):
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=20) as r: body=r.read(2_000_000).decode(errors="replace")
    title=re.search(r"<title[^>]*>(.*?)</title>",body,re.I|re.S)
    title=re.sub(r"\s+"," ",title.group(1)).strip() if title else url
    item={"source":"manual","external_id":hashlib.sha256(url.encode()).hexdigest()[:24],"url":url,"title":title}
    item.update(infer(title,body[:100000])); con=db.connect(cfg["app"]["database"]); db.upsert(con,item,now()); rescore(con,cfg); con.commit(); print("Annonce ajoutée.")

def rescore(con,cfg):
    for row in con.execute("SELECT * FROM listings"):
        item=dict(row); lt,fs,overall,rec=score(item,cfg)
        con.execute("UPDATE listings SET long_term_score=?,four_six_year_score=?,overall_score=?,recommendation=? WHERE id=?",(lt,fs,overall,rec,row["id"]))

def dashboard(cfg):
    con=db.connect(cfg["app"]["database"]); rescore(con,cfg); con.commit(); build(con,cfg["app"]["dashboard"],now()); print(cfg["app"]["dashboard"])

def main(argv=None):
    p=argparse.ArgumentParser(description="Veille de VUS usages au Quebec"); p.add_argument("--config",default="config.toml")
    sp=p.add_subparsers(dest="cmd",required=True); sp.add_parser("init"); sp.add_parser("collect"); sp.add_parser("dashboard"); a=sp.add_parser("add-url"); a.add_argument("url")
    args=p.parse_args(argv); cfg=config(args.config)
    if args.cmd=="init": db.connect(cfg["app"]["database"]).close(); print("Base initialisée.")
    elif args.cmd=="collect": run_collect(cfg); dashboard(cfg)
    elif args.cmd=="dashboard": dashboard(cfg)
    else: add_url(cfg,args.url); dashboard(cfg)
if __name__=="__main__": main()
