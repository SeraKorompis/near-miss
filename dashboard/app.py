"""Near-Miss dashboard.

    streamlit run dashboard/app.py

Reads output/results.json, output/recommendations.json and output/<video>/annotated.mp4.
Regenerate them with: ./run_demo.sh --no-show && python analysis/nearmiss.py && python analysis/recommend.py
"""
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

# Categorical slots 1-2 of the validated reference palette (blue = bought, orange = near-miss)
BOUGHT, NEAR_MISS = "#2a78d6", "#eb6834"
PRIORITY_ICON = {"high": "🔴 High", "medium": "🟠 Medium", "low": "🟢 Low"}
OUTCOME_LABEL = {
    "near_miss_put_back": "Picked up, put back",
    "near_miss_looked": "Looked, never touched",
    "purchase": "Bought",
    "glance": "Glance",
}

st.set_page_config(page_title="Near-Miss", page_icon="👀", layout="wide")


@st.cache_data
def load():
    results = json.loads((OUT / "results.json").read_text())
    recs_path = OUT / "recommendations.json"
    recs = json.loads(recs_path.read_text()) if recs_path.exists() else {}
    return results, recs


if not (OUT / "results.json").exists():
    st.error("No results yet. Run: `./run_demo.sh --no-show && python analysis/nearmiss.py && python analysis/recommend.py`")
    st.stop()

results, recs = load()
summary, products = results["summary"], results["products"]
moments = pd.DataFrame(results["moments"])

st.title("Near-Miss")
st.caption("The sales you almost won: products shoppers looked at or picked up, but didn't buy. "
           f"Interest = looked ≥ {summary['dwell_threshold_s']}s or touched.")

# --- Headline numbers ---------------------------------------------------------------------------
c = st.columns(4)
c[0].metric("Shoppers tracked", summary["shoppers"])
c[1].metric("Purchases", summary["purchases"])
c[2].metric("Near-misses", summary["near_misses"])
c[3].metric("Interest → purchase", f"{summary['conversion_rate']:.0%}")

st.divider()

# --- Ranked products + chart ---------------------------------------------------------------------
left, right = st.columns([1.25, 1])
with left:
    st.subheader("Products ranked by near-misses")
    table = pd.DataFrame([{
        "Product": p["product_id"],
        "Interested": p["shoppers_interested"],
        "Bought": p["purchases"],
        "Near-misses": p["near_misses"],
        "Near-miss rate": p["near_miss_rate"],
        "Avg attention (s)": p["avg_dwell_s"],
        "Priority": PRIORITY_ICON.get(recs.get(p["product_id"], {}).get("priority", ""), "-"),
    } for p in products])
    st.dataframe(
        table, hide_index=True, use_container_width=True,
        column_config={
            "Near-miss rate": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
            "Avg attention (s)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

with right:
    st.subheader("Interested shoppers: bought vs walked away")
    names = [p["product_id"] for p in products][::-1]
    bought = [p["purchases"] for p in products][::-1]
    missed = [p["near_misses"] for p in products][::-1]
    fig = go.Figure()
    fig.add_bar(y=names, x=bought, name="Bought", orientation="h", marker_color=BOUGHT,
                marker_line_width=2, marker_line_color="rgba(255,255,255,0.9)",
                hovertemplate="%{y}: %{x} bought<extra></extra>")
    fig.add_bar(y=names, x=missed, name="Near-miss", orientation="h", marker_color=NEAR_MISS,
                marker_line_width=2, marker_line_color="rgba(255,255,255,0.9)",
                hovertemplate="%{y}: %{x} near-miss<extra></extra>")
    fig.update_layout(barmode="stack", height=300, margin=dict(l=0, r=10, t=10, b=0),
                      legend=dict(orientation="h", y=1.12, x=0, traceorder="normal"), bargap=0.45,
                      xaxis=dict(title="Shoppers", dtick=1, gridcolor="rgba(128,128,128,0.2)"),
                      yaxis=dict(title=None), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

# --- AI recommendations --------------------------------------------------------------------------
st.subheader("What to do about it")
if not recs:
    st.info("No recommendations yet - run `python analysis/recommend.py`.")
else:
    cols = st.columns(min(3, len(products)) or 1)
    shown = [p for p in products if p["product_id"] in recs][:6]
    for i, p in enumerate(shown):
        r = recs[p["product_id"]]
        with cols[i % len(cols)].container(border=True):
            st.markdown(f"**{p['product_id']}** · {PRIORITY_ICON.get(r['priority'], r['priority'])}")
            st.write(r["diagnosis"])
            st.markdown(f"**Try:** {r['action']}")
            st.caption(f"{p['near_misses']} near-miss · {p['purchases']} bought · source: {r.get('source', '')}")

st.divider()

# --- Near-miss moments with video --------------------------------------------------------------
st.subheader("Near-miss moments")
nm = moments[moments.outcome.str.startswith("near_miss")].copy()
if nm.empty:
    st.write("No near-misses found.")
else:
    nm["What happened"] = nm.outcome.map(OUTCOME_LABEL)
    labels = [f"{r.video} · {r.product_id} · {r['What happened'].lower()} · {r.dwell_s:.1f}s at {r.start_s:.1f}s"
              for _, r in nm.iterrows()]
    vcol, lcol = st.columns([1.4, 1])
    with lcol:
        pick = st.radio("Pick a moment to replay", range(len(nm)), format_func=lambda i: labels[i])
        row = nm.iloc[pick]
        st.markdown(f"**{row.product_id}**: {row['What happened'].lower()}")
        st.write(f"Attention {row.dwell_s:.1f}s, from {row.start_s:.1f}s to {row.end_s:.1f}s. Not bought.")
    with vcol:
        video = OUT / row.video / "annotated.mp4"
        if video.exists():
            st.video(str(video), start_time=int(row.start_s))
        else:
            st.warning(f"{video} not found - run ./run_demo.sh {row.video} --no-show")

with st.expander("All tracked moments (incl. purchases and glances)"):
    allm = moments.copy()
    allm["What happened"] = allm.outcome.map(OUTCOME_LABEL)
    st.dataframe(allm[["video", "product_id", "What happened", "dwell_s", "start_s", "end_s", "touched", "bought"]],
                 hide_index=True, use_container_width=True)

with st.expander("Watch a full video"):
    vids = sorted(p.parent.name for p in OUT.glob("*/annotated.mp4"))
    if vids:
        v = st.selectbox("Video", vids)
        st.video(str(OUT / v / "annotated.mp4"))
