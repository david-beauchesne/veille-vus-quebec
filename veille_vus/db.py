import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
 id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
 url TEXT NOT NULL, make TEXT, model TEXT, trim TEXT, year INTEGER, price INTEGER,
 mileage INTEGER, location TEXT, seller_type TEXT, seller_name TEXT,
 transmission TEXT, drivetrain TEXT, fuel TEXT, accident_history TEXT,
 owners INTEGER, carfax INTEGER, title TEXT, first_seen TEXT NOT NULL,
 last_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', raw_json TEXT,
 long_term_score REAL, four_six_year_score REAL, overall_score REAL,
 recommendation TEXT, UNIQUE(source, external_id), UNIQUE(url)
);
CREATE TABLE IF NOT EXISTS price_history (
 id INTEGER PRIMARY KEY, listing_id INTEGER NOT NULL REFERENCES listings(id),
 observed_at TEXT NOT NULL, price INTEGER NOT NULL,
 UNIQUE(listing_id, observed_at, price)
);
CREATE INDEX IF NOT EXISTS idx_listing_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_price_listing ON price_history(listing_id);
"""

def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    columns={row[1] for row in con.execute("PRAGMA table_info(listings)")}
    migrations={
      "verification_status":"TEXT NOT NULL DEFAULT 'unverified'",
      "data_confidence":"REAL NOT NULL DEFAULT 0",
      "field_provenance":"TEXT", "verified_at":"TEXT", "verification_error":"TEXT"
      ,"in_scope":"INTEGER NOT NULL DEFAULT 1"
    }
    for name,definition in migrations.items():
        if name not in columns: con.execute(f"ALTER TABLE listings ADD COLUMN {name} {definition}")
    return con

def upsert(con, item, seen_at):
    keys = ["source","external_id","url","make","model","trim","year","price","mileage",
            "location","seller_type","seller_name","transmission","drivetrain","fuel",
            "accident_history","owners","carfax","title","verification_status","data_confidence",
            "field_provenance","verified_at","verification_error"]
    keys.append("in_scope")
    defaults={"in_scope":1,"verification_status":"unverified","data_confidence":0.0}
    values = [item.get(k,defaults.get(k)) for k in keys]
    con.execute(f"""INSERT INTO listings ({','.join(keys)},first_seen,last_seen,status,raw_json)
      VALUES ({','.join('?' for _ in keys)},?,?,'active',?)
      ON CONFLICT(source,external_id) DO UPDATE SET
      url=excluded.url, make=COALESCE(excluded.make,listings.make),
      model=COALESCE(excluded.model,listings.model), trim=COALESCE(excluded.trim,listings.trim),
      year=COALESCE(excluded.year,listings.year), price=COALESCE(excluded.price,listings.price),
      mileage=COALESCE(excluded.mileage,listings.mileage),
      location=COALESCE(excluded.location,listings.location), last_seen=excluded.last_seen,
      status='active', title=COALESCE(excluded.title,listings.title), raw_json=excluded.raw_json,
      verification_status=excluded.verification_status,data_confidence=excluded.data_confidence,
      field_provenance=excluded.field_provenance,verified_at=excluded.verified_at,
      verification_error=excluded.verification_error,in_scope=excluded.in_scope""",
      values + [seen_at, seen_at, json.dumps(item, ensure_ascii=False)])
    row = con.execute("SELECT id, first_seen FROM listings WHERE source=? AND external_id=?",
                      (item["source"], item["external_id"])).fetchone()
    if item.get("price"):
        con.execute("INSERT OR IGNORE INTO price_history(listing_id,observed_at,price) VALUES(?,?,?)",
                    (row["id"], seen_at, item["price"]))
    return row["id"], row["first_seen"] == seen_at
