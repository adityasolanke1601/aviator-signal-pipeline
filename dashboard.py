"""
dashboard.py — funnel instrumentation for the enrichment pipeline.

Run: streamlit run dashboard.py
Loads results.csv (output of main.py) and shows ranked fit scores,
signal breakdowns, and lets you eyeball which orgs are worth a sequencer slot.
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Aviator Signal Pipeline", layout="wide")
st.title("GTM Signal Pipeline — Results")

uploaded = st.file_uploader("Upload results.csv", type="csv")
df = pd.read_csv(uploaded) if uploaded else None

if df is None:
    try:
        df = pd.read_csv("results.csv")
        st.caption("Loaded results.csv from working directory")
    except FileNotFoundError:
        st.info("Run `python main.py --orgs ...` first, or upload a results.csv above.")
        st.stop()

min_score = st.slider("Minimum fit score", 0, 100, 0)
filtered = df[df["fit_score"] >= min_score].sort_values("fit_score", ascending=False)

col1, col2, col3 = st.columns(3)
col1.metric("Orgs above threshold", len(filtered))
col2.metric("Avg fit score", round(filtered["fit_score"].mean(), 1) if len(filtered) else 0)
col3.metric("Avg PR throughput (30d)", round(filtered["pr_throughput_30d"].mean(), 1) if len(filtered) else 0)

st.bar_chart(filtered.set_index("org")["fit_score"])

st.subheader("Ranked accounts")
st.dataframe(
    filtered[["org", "fit_score", "biggest_repo", "total_size_kb",
              "ci_adoption_pct", "pr_throughput_30d", "languages"]],
    use_container_width=True,
)

st.subheader("Outbound preview")
selected = st.selectbox("Pick an org", filtered["org"].tolist())
if selected:
    row = filtered[filtered["org"] == selected].iloc[0]
    st.text_area("Generated message", row.get("outbound_message", ""), height=180)
