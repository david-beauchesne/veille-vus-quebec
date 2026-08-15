import json
from pathlib import Path

def build(con, path, generated_at):
    rows=[]
    for r in con.execute("""SELECT l.*,
      (SELECT MIN(price) FROM price_history p WHERE p.listing_id=l.id) min_price,
      (SELECT MAX(price) FROM price_history p WHERE p.listing_id=l.id) max_price,
      (SELECT COUNT(*) FROM price_history p WHERE p.listing_id=l.id) price_points
      FROM listings l ORDER BY overall_score DESC, last_seen DESC"""):
        d=dict(r); d.pop("raw_json",None); rows.append(d)
    data=json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    template=Path(__file__).with_name("template.html").read_text()
    out=template.replace("__DATA__",data).replace("__GENERATED__",generated_at)
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(out)

