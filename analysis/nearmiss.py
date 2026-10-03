"""Combine attention events with the till log -> near-misses per product.

    python analysis/nearmiss.py            # reads output/<video>/attention_events.csv
    -> output/results.json

Per shopper and product:
  purchase              bought it
  near-miss (put back)  touched / picked it up, didn't buy
  near-miss (looked)    looked >= DWELL_THRESHOLD_S in total, didn't touch, didn't buy
  glance                anything shorter - not counted as interest
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DWELL_THRESHOLD_S = 2.5
VIDEOS = ["IMG_9470", "IMG_9472", "IMG_9473"]


def load_attention(videos, output_dir):
    frames = []
    for v in videos:
        path = output_dir / v / "attention_events.csv"
        if not path.exists():
            print(f"  missing {path} - run ./run_demo.sh {v} --no-show first")
            continue
        df = pd.read_csv(path)
        df["video"] = v
        frames.append(df)
    if not frames:
        raise SystemExit("No attention events found.")
    return pd.concat(frames, ignore_index=True)


def classify(row):
    if row.bought:
        return "purchase"
    if row.touched:
        return "near_miss_put_back"
    if row.dwell_s >= DWELL_THRESHOLD_S:
        return "near_miss_looked"
    return "glance"


def build(events, till):
    # One row per shopper x product: total dwell, touched?, first moment
    g = events.groupby(["video", "person_id", "product_id"]).agg(
        dwell_s=("dwell_s", "sum"), touched=("touched", "max"), first_s=("start_s", "min"),
        last_s=("end_s", "max")).reset_index()
    g = g.merge(till, on=["video", "person_id", "product_id"], how="left")
    g["bought"] = g["bought"].fillna(0).astype(int)
    g["touched"] = g["touched"].astype(int)
    g["outcome"] = g.apply(classify, axis=1)
    g["shopper"] = g["video"] + " #" + g["person_id"].astype(str)

    interested = g[g.outcome != "glance"]
    products = []
    for product, rows in g.groupby("product_id"):
        inter = rows[rows.outcome != "glance"]
        n_int = len(inter)
        purchases = int((rows.outcome == "purchase").sum())
        put_back = int((rows.outcome == "near_miss_put_back").sum())
        looked = int((rows.outcome == "near_miss_looked").sum())
        near = put_back + looked
        products.append({
            "product_id": product,
            "shoppers_noticed": int(len(rows)),
            "shoppers_interested": n_int,
            "purchases": purchases,
            "near_misses": near,
            "near_miss_put_back": put_back,
            "near_miss_looked": looked,
            "touches": int(rows.touched.sum()),
            "near_miss_rate": round(near / n_int, 3) if n_int else 0.0,
            "conversion_rate": round(purchases / n_int, 3) if n_int else 0.0,
            "avg_dwell_s": round(float(inter.dwell_s.mean()), 1) if n_int else round(float(rows.dwell_s.mean()), 1),
            "total_dwell_s": round(float(rows.dwell_s.sum()), 1),
        })
    products.sort(key=lambda p: (-p["near_misses"], -p["near_miss_put_back"], -p["near_miss_rate"], -p["total_dwell_s"]))

    moments = [
        {"shopper": r.shopper, "video": r.video, "product_id": r.product_id, "outcome": r.outcome,
         "dwell_s": round(float(r.dwell_s), 1), "start_s": round(float(r.first_s), 1),
         "end_s": round(float(r.last_s), 1), "touched": int(r.touched), "bought": int(r.bought)}
        for r in g.sort_values(["video", "first_s"]).itertuples()
    ]
    n_shoppers = g.shopper.nunique()
    total_near = sum(p["near_misses"] for p in products)
    total_buy = sum(p["purchases"] for p in products)
    summary = {
        "shoppers": int(n_shoppers),
        "interested_pairs": int(len(interested)),
        "purchases": total_buy,
        "near_misses": total_near,
        "conversion_rate": round(total_buy / len(interested), 3) if len(interested) else 0.0,
        "dwell_threshold_s": DWELL_THRESHOLD_S,
    }
    return {"summary": summary, "products": products, "moments": moments}


def main():
    events = load_attention(VIDEOS, ROOT / "output")
    till = pd.read_csv(ROOT / "analysis" / "till_log.csv")
    results = build(events, till)
    out = ROOT / "output" / "results.json"
    out.write_text(json.dumps(results, indent=2))

    s = results["summary"]
    print(f"{s['shoppers']} shoppers, {s['purchases']} purchases, {s['near_misses']} near-misses "
          f"(conversion {s['conversion_rate']:.0%})")
    print(f"{'product':<22}{'interested':>11}{'bought':>8}{'near-miss':>10}{'rate':>7}{'avg dwell':>11}")
    for p in results["products"]:
        print(f"{p['product_id']:<22}{p['shoppers_interested']:>11}{p['purchases']:>8}{p['near_misses']:>10}"
              f"{p['near_miss_rate']:>7.0%}{p['avg_dwell_s']:>10.1f}s")
    print("\nNear-miss moments:")
    for m in results["moments"]:
        if m["outcome"].startswith("near_miss"):
            how = "picked up, put back" if m["outcome"] == "near_miss_put_back" else "looked, didn't touch"
            print(f"  {m['shopper']:<12} {m['product_id']:<22} {m['start_s']:>5.1f}s  {m['dwell_s']:.1f}s  ({how})")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
