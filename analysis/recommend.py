"""Suggest an action per product from its near-miss numbers, using a local Ollama model.

    python analysis/recommend.py                  # gemma3:12b by default
    NEARMISS_MODEL=llama3.2:3b python analysis/recommend.py
    python analysis/recommend.py --rules          # skip the LLM, rule-based only

Reads output/results.json and writes output/recommendations.json, so the
dashboard never waits for the model. Falls back to rules if Ollama isn't running.
"""
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("NEARMISS_MODEL", "gemma3:12b")

PROMPT = """You are a retail merchandising analyst. A camera system measured how shoppers
behaved in front of one product on a shelf, and a till log shows what they bought.

Product: {product_id}
Shoppers who showed interest (looked {threshold}s+ or touched it): {shoppers_interested}
Bought it: {purchases}
Near-misses: {near_misses}  (picked it up and put it back: {near_miss_put_back}; looked but never touched: {near_miss_looked})
Near-miss rate: {near_miss_rate:.0%}
Average attention time of interested shoppers: {avg_dwell_s}s

Interpretation hints: picked up then put back usually points to price, pack information
or ingredients seen on the back; long looking without touching points to shelf position,
reachability, unclear packaging or price visibility; high conversion means it works.

Reply with JSON only, exactly these keys:
{{"diagnosis": "<one short sentence: what the numbers say>",
  "action": "<one concrete thing the brand or store should test next>",
  "priority": "high" | "medium" | "low"}}"""


def rule_based(p):
    if p["shoppers_interested"] == 0:
        return {"diagnosis": "Only brief glances - the product isn't drawing real attention.",
                "action": "Improve visibility: move to eye level or add a shelf talker.", "priority": "low"}
    if p["near_miss_put_back"] > 0 and p["near_miss_put_back"] >= p["near_miss_looked"]:
        return {"diagnosis": "Shoppers pick it up and put it back - interest dies after a closer look.",
                "action": "Test a lower price point or clearer pack info (benefits, ingredients) on the front.",
                "priority": "high"}
    if p["near_miss_looked"] > 0 and p["purchases"] == 0:
        return {"diagnosis": "Shoppers look for a long time but never reach for it.",
                "action": "Make it easier to reach and compare: lower shelf position and visible price tag.",
                "priority": "high" if p["near_miss_rate"] >= 0.5 else "medium"}
    if p["conversion_rate"] >= 0.5:
        return {"diagnosis": "Strong performer - most interested shoppers buy it.",
                "action": "Protect it: keep stock full and consider more facings.", "priority": "low"}
    return {"diagnosis": "Mixed results - some interest converts, some walks away.",
            "action": "A/B test a promotion against the current price.", "priority": "medium"}


def ask_llm(p, threshold):
    import ollama
    reply = ollama.chat(model=MODEL, format="json", options={"temperature": 0.2},
                        messages=[{"role": "user", "content": PROMPT.format(threshold=threshold, **p)}])
    data = json.loads(reply["message"]["content"])
    out = {k: str(data.get(k, "")).strip() for k in ("diagnosis", "action", "priority")}
    if not out["diagnosis"] or not out["action"]:
        raise ValueError("incomplete reply")
    if out["priority"] not in ("high", "medium", "low"):
        out["priority"] = rule_based(p)["priority"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", action="store_true", help="rule-based only, no LLM")
    args = ap.parse_args()

    results = json.loads((ROOT / "output" / "results.json").read_text())
    threshold = results["summary"]["dwell_threshold_s"]
    recs = {}
    for p in results["products"]:
        rec, source = None, "rules"
        if not args.rules and p["shoppers_interested"] > 0:
            try:
                rec, source = ask_llm(p, threshold), f"ollama:{MODEL}"
            except Exception as e:  # Ollama not running, model missing, bad JSON...
                print(f"  {p['product_id']}: LLM failed ({e.__class__.__name__}: {e}) - using rules")
        rec = rec or rule_based(p)
        rec["source"] = source
        recs[p["product_id"]] = rec
        print(f"[{rec['priority']:>6}] {p['product_id']:<22} {rec['action']}  ({source})")

    out = ROOT / "output" / "recommendations.json"
    out.write_text(json.dumps(recs, indent=2))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
