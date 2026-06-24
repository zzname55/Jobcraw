from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH
from database.db import JobDatabase


st.set_page_config(page_title="AI Job Automation", layout="wide")
st.title("AI Job Automation Dashboard")

db = JobDatabase(DB_PATH)
db.init()
jobs = db.fetch_jobs(min_score=0)
frame = pd.DataFrame([job.to_record() for job in jobs])

if frame.empty:
    st.info("No jobs stored yet. Run the CLI first.")
    st.stop()

with st.sidebar:
    min_score = st.slider("Minimum score", 0, 100, 60)
    region = st.multiselect("Region", sorted(frame["region"].dropna().unique()))
    country = st.multiselect("Country", sorted(frame["country"].dropna().unique()))
    remote_type = st.multiselect("Remote type", sorted(frame["remote_type"].dropna().unique()))
    seniority = st.multiselect("Seniority", sorted(frame["seniority"].dropna().unique()))
    language = st.multiselect("Language", sorted(frame["language"].dropna().unique()))
    source = st.multiselect("Source", sorted(frame["source_platform"].dropna().unique()))
    priority = st.multiselect("Priority", sorted(frame["priority_level"].dropna().unique()))

filtered = frame[frame["relevance_score"] >= min_score].copy()
for column, values in {
    "region": region,
    "country": country,
    "remote_type": remote_type,
    "seniority": seniority,
    "language": language,
    "source_platform": source,
    "priority_level": priority,
}.items():
    if values:
        filtered = filtered[filtered[column].isin(values)]

filtered = filtered.sort_values("relevance_score", ascending=False)

left, middle, right = st.columns(3)
left.metric("Jobs", len(filtered))
middle.metric("Urgent", int((filtered["priority_level"] == "urgent").sum()))
right.metric("Average score", round(float(filtered["relevance_score"].mean()), 1) if not filtered.empty else 0)

st.dataframe(
    filtered[
        [
            "relevance_score",
            "priority_level",
            "job_title",
            "company_name",
            "location",
            "remote_type",
            "seniority",
            "language",
            "source_platform",
            "job_url",
            "application_status",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Download CSV",
    filtered.to_csv(index=False).encode("utf-8"),
    file_name="filtered_jobs.csv",
    mime="text/csv",
)

st.subheader("Update status")
job_id = st.number_input("Job ID", min_value=1, step=1)
status = st.selectbox("Status", ["new", "saved", "applied", "ignored"])
if st.button("Update"):
    db.update_status(int(job_id), status)
    st.success("Status updated.")
