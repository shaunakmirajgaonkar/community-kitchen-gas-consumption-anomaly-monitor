from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    DISPLAY_NAMES,
    REQUIRED_COLUMNS,
    add_derived_metrics,
    driver_summary,
    make_summary,
    markdown_table,
    scenario_score,
    validate_columns,
)

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_PATH = BASE_DIR / "data" / "sample_community_kitchen_gas.csv"

st.set_page_config(
    page_title="Community Kitchen Gas-Consumption Anomaly Monitor",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --ink:#17324d; --muted:#61748a; --paper:#ffffff; --bg:#f4f8fc; --line:#dce7f1; --accent:#f97316; --accent2:#0ea5e9; --good:#16a34a; --warn:#d97706; --bad:#dc2626; }
    .stApp { background: linear-gradient(180deg,#f8fbff 0%,#eef5fb 100%); color:var(--ink); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg,#ffffff 0%,#edf6ff 100%); border-right:1px solid var(--line); }
    [data-testid="stSidebar"] * { color:var(--ink) !important; }
    .hero { background:linear-gradient(115deg,#fff7ed 0%,#ffffff 50%,#eff6ff 100%); border:1px solid #e5eaf0; border-radius:24px; padding:26px 28px; box-shadow:0 12px 30px rgba(26,55,84,.08); }
    .hero h1 { margin:0; color:#17324d; font-size:2.2rem; letter-spacing:-.03em; }
    .hero p { color:#5b7187; margin:.45rem 0 0; font-size:1.02rem; }
    .pill { display:inline-block; padding:6px 11px; border-radius:999px; font-size:.78rem; font-weight:700; margin-bottom:10px; background:#fff2e8; color:#b45309; border:1px solid #fed7aa; }
    .section { background:#fff; border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 8px 20px rgba(31,53,75,.05); }
    .metric { background:#fff; border:1px solid var(--line); border-radius:16px; padding:16px 18px; min-height:110px; box-shadow:0 8px 18px rgba(31,53,75,.05); }
    .metric .label { color:#667b90; font-size:.82rem; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }
    .metric .value { color:#17324d; font-size:2rem; font-weight:800; line-height:1.15; }
    .metric .hint { color:#7a8da0; font-size:.82rem; margin-top:5px; }
    .note { background:#f8fbff; border:1px solid #d7e6f3; padding:12px 14px; border-radius:12px; color:#50657a; }
    .small { color:#718397; font-size:.82rem; }
    div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
    .stButton > button, .stDownloadButton > button { border-radius:11px; border:1px solid #cbd8e5; }
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi(label: str, value: str, hint: str = "") -> None:
    st.markdown(
        f"<div class='metric'><div class='label'>{label}</div><div class='value'>{value}</div><div class='hint'>{hint}</div></div>",
        unsafe_allow_html=True,
    )


def load_data() -> pd.DataFrame:
    if "uploaded_df" not in st.session_state:
        try:
            st.session_state.uploaded_df = pd.read_csv(SAMPLE_PATH)
        except Exception as exc:
            st.error(f"Could not load bundled sample data: {exc}")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    return st.session_state.uploaded_df.copy()


st.markdown(
    """
    <div class='hero'>
      <div class='pill'>LOCAL-FIRST • COMMUNITY KITCHEN OPERATIONS</div>
      <h1>Community Kitchen Gas-Consumption Anomaly Monitor</h1>
      <p>Transparent screening of possible LPG-use anomalies, equipment-condition signals, supply pressure, and usage patterns using locally supplied operational records.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("### 🔥 Control Center")
st.sidebar.caption("100% local processing • CSV in / CSV out")

uploaded = st.sidebar.file_uploader("Upload kitchen gas CSV", type=["csv"], help="Required fields are listed in DATA_DICTIONARY.md")
if uploaded is not None:
    try:
        candidate = pd.read_csv(uploaded)
        missing = validate_columns(candidate)
        if missing:
            st.sidebar.error("Missing columns: " + ", ".join(missing))
        else:
            st.session_state.uploaded_df = candidate
            st.sidebar.success(f"Loaded {len(candidate):,} records")
    except Exception as exc:
        st.sidebar.error(f"CSV could not be read: {exc}")

if st.sidebar.button("↺ Reset to bundled sample"):
    st.session_state.uploaded_df = pd.read_csv(SAMPLE_PATH)
    st.rerun()

raw = load_data()
missing = validate_columns(raw)
if missing:
    st.error("Dataset is missing required columns: " + ", ".join(missing))
    st.stop()

try:
    df = add_derived_metrics(raw)
except Exception as exc:
    st.error(f"Could not calculate screening metrics: {exc}")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.markdown("### Filters")
community_options = sorted(df["community"].astype(str).unique().tolist())
selected_communities = st.sidebar.multiselect("Communities", community_options, default=community_options)
class_options = ["Low", "Moderate", "High", "Critical"]
selected_classes = st.sidebar.multiselect("Screening class", class_options, default=class_options)
min_score, max_score = st.sidebar.slider("Score range", 0.0, 100.0, (0.0, 100.0), 1.0)

view = df[
    df["community"].astype(str).isin(selected_communities)
    & df["screening_classification"].isin(selected_classes)
    & df["gas_anomaly_screening_score"].between(min_score, max_score)
].copy()

st.sidebar.caption(f"Active records: {len(view):,} / {len(df):,}")

pages = [
    "Overview",
    "Anomaly Matrix",
    "Consumption & Meals",
    "Equipment Condition",
    "Supply & Deliveries",
    "Kitchen Profiles",
    "Priority Queue",
    "Scenario Lab",
    "Reports & Export",
    "Data Explorer",
]
page = st.sidebar.radio("Navigation", pages)

if view.empty:
    st.warning("No records match the current filters. Adjust the sidebar filters to continue.")
    st.stop()

summary = make_summary(view)

if page == "Overview":
    cols = st.columns(4)
    with cols[0]: kpi("Kitchens", f"{len(view):,}", "active records")
    with cols[1]: kpi("Average score", f"{summary['avg_score']:.1f}", "0–100 screening")
    with cols[2]: kpi("Priority records", f"{summary['priority_count']:,}", "review or monitoring signal")
    with cols[3]: kpi("Top driver", str(summary["top_driver"]), "most frequent dominant signal")

    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.markdown("<div class='section'><h3>Screening distribution</h3>", unsafe_allow_html=True)
        counts = view["screening_classification"].value_counts().reindex(class_options, fill_value=0).reset_index()
        counts.columns = ["Classification", "Count"]
        fig = px.bar(counts, x="Classification", y="Count", text_auto=True)
        fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor="white", plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='section'><h3>Screening score by community</h3>", unsafe_allow_html=True)
        community_scores = view.groupby("community", as_index=False)["gas_anomaly_screening_score"].mean().sort_values("gas_anomaly_screening_score", ascending=False)
        fig = px.bar(community_scores, x="gas_anomaly_screening_score", y="community", orientation="h", text_auto=".1f")
        fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor="white", plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section'><h3>Operational signal cards</h3>", unsafe_allow_html=True)
    r = st.columns(4)
    with r[0]: kpi("Odor flags", f"{summary['odor_flags']:,}", "reported odor events")
    with r[1]: kpi("Supply flags", f"{summary['supply_flags']:,}", "delivery/balance pressure")
    with r[2]: kpi("Equipment flags", f"{summary['equipment_flags']:,}", "condition pressure")
    with r[3]: kpi("Communities", f"{summary['communities']:,}", "represented in filtered view")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='section'><h3>Highest screening records</h3>", unsafe_allow_html=True)
    cols_to_show = ["kitchen_id", "community", "gas_anomaly_screening_score", "screening_classification", "dominant_driver", "review_priority"]
    st.dataframe(view[cols_to_show].sort_values("gas_anomaly_screening_score", ascending=False).head(12), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Anomaly Matrix":
    st.markdown("<div class='section'><h3>Multi-signal anomaly matrix</h3><p class='small'>Compare the four explainable screening components across kitchens.</p>", unsafe_allow_html=True)
    heat = view.set_index("kitchen_id")[["consumption_pressure_score","equipment_condition_pressure_score","supply_pressure_score","usage_signal_score","gas_anomaly_screening_score"]].head(30)
    heat.columns = ["Consumption", "Equipment", "Supply", "Usage", "Overall"]
    fig = px.imshow(heat.T, aspect="auto", color_continuous_scale="Oranges")
    fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Consumption & Meals":
    st.markdown("<div class='section'><h3>Consumption intelligence</h3>", unsafe_allow_html=True)
    a,b,c = st.columns(3)
    with a: kpi("Avg LPG / meal", f"{view['lpg_per_meal'].mean():.3f} kg", "screening efficiency signal")
    with b: kpi("Avg meals/day", f"{view['meals_per_day'].mean():.1f}", "operational volume")
    with c: kpi("Avg cooking time", f"{view['cooking_hours_day'].mean():.1f} h", "daily cooking duration")
    fig = px.scatter(view, x="meals_served", y="lpg_kg_used", size="gas_anomaly_screening_score", color="screening_classification", hover_name="kitchen_id")
    fig.update_layout(margin=dict(l=10,r=10,t=25,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Equipment Condition":
    st.markdown("<div class='section'><h3>Equipment-condition review</h3><p class='small'>Lower condition scores create higher screening pressure.</p>", unsafe_allow_html=True)
    equipment = pd.DataFrame({
        "Metric": ["Stove", "Regulator", "Hose", "Storage"],
        "Average condition": [
            view["stove_condition_score"].mean(),
            view["regulator_condition_score"].mean(),
            view["hose_condition_score"].mean(),
            view["storage_condition_score"].mean(),
        ],
    })
    fig = px.bar(equipment, x="Metric", y="Average condition", range_y=[0,100], text_auto=".1f")
    fig.update_layout(margin=dict(l=10,r=10,t=25,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(view[["kitchen_id","community","equipment_condition_pressure_score","stove_condition_score","regulator_condition_score","hose_condition_score","storage_condition_score","equipment_flag"]].sort_values("equipment_condition_pressure_score", ascending=False), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Supply & Deliveries":
    st.markdown("<div class='section'><h3>Supply and delivery pressure</h3>", unsafe_allow_html=True)
    fig = px.scatter(view, x="delivery_gap_days", y="lpg_balance_kg", size="lpg_kg_used", color="screening_classification", hover_name="kitchen_id")
    fig.update_layout(margin=dict(l=10,r=10,t=25,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    supply_cols = ["kitchen_id","community","lpg_delivered_kg","lpg_kg_used","lpg_balance_kg","delivery_gap_days","supply_pressure_score","supply_flag"]
    st.dataframe(view[supply_cols].sort_values("supply_pressure_score", ascending=False), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Kitchen Profiles":
    st.markdown("<div class='section'><h3>Community and kitchen profiles</h3>", unsafe_allow_html=True)
    profile = view.groupby("community").agg(
        Kitchens=("kitchen_id","count"),
        Avg_Score=("gas_anomaly_screening_score","mean"),
        Avg_LPG=("lpg_kg_used","mean"),
        Avg_Meals=("meals_served","mean"),
        Priority=("review_priority", lambda s: int((s != "Monitor").sum())),
    ).reset_index().sort_values("Avg_Score", ascending=False)
    profile["Avg_Score"] = profile["Avg_Score"].round(1)
    st.dataframe(profile, use_container_width=True, hide_index=True)
    ds = driver_summary(view)
    fig = px.bar(ds, x="Average score", y="Driver", orientation="h", text_auto=".1f")
    fig.update_layout(margin=dict(l=10,r=10,t=25,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Priority Queue":
    st.markdown("<div class='section'><h3>Priority queue</h3><p class='small'>Ordered screening signals for operational review. This is not a leak confirmation or safety certification.</p>", unsafe_allow_html=True)
    queue_cols = ["kitchen_id","community","gas_anomaly_screening_score","screening_classification","dominant_driver","review_priority","odor_flag","supply_flag","equipment_flag","efficiency_flag"]
    queue = view[queue_cols].sort_values(["gas_anomaly_screening_score","kitchen_id"], ascending=[False, True])
    st.dataframe(queue, use_container_width=True, hide_index=True)
    st.download_button("Download priority queue CSV", queue.to_csv(index=False).encode(), "priority_queue.csv", "text/csv")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Scenario Lab":
    st.markdown("<div class='section'><h3>Scenario Lab</h3><p class='small'>Explore modeled changes to one kitchen. Scenarios are analytical what-if views, not predictions.</p>", unsafe_allow_html=True)
    selected_kitchen = st.selectbox("Kitchen", view["kitchen_id"].tolist())
    base = view.loc[view["kitchen_id"] == selected_kitchen].iloc[0]
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1: usage = st.slider("Usage multiplier", 0.50, 1.80, 1.00, 0.05)
    with sc2: cond = st.slider("Condition score delta", -30.0, 20.0, 0.0, 1.0)
    with sc3: gap = st.slider("Delivery gap delta", -14.0, 20.0, 0.0, 1.0)
    with sc4: odors = st.slider("Odor events delta", -2, 5, 0, 1)
    reference_benchmark = max(float(df["lpg_per_meal"].median()), 0.02)
    base_score = scenario_score(base, benchmark_lpg_per_meal=reference_benchmark)
    scenario = scenario_score(
        base,
        usage_multiplier=usage,
        equipment_condition_delta=cond,
        delivery_gap_delta=gap,
        odor_events_delta=odors,
        benchmark_lpg_per_meal=reference_benchmark,
    )
    m1,m2,m3 = st.columns(3)
    with m1: kpi("Baseline", f"{base_score:.1f}", base["screening_classification"])
    with m2: kpi("Scenario", f"{scenario:.1f}", "modeled score")
    with m3: kpi("Change", f"{scenario-base_score:+.1f}", "scenario − baseline")
    compare = pd.DataFrame({"State":["Baseline","Scenario"],"Score":[base_score,scenario]})
    fig = px.bar(compare, x="State", y="Score", range_y=[0,100], text_auto=".1f")
    fig.update_layout(margin=dict(l=10,r=10,t=25,b=10), paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Reports & Export":
    st.markdown("<div class='section'><h3>Report-ready export</h3>", unsafe_allow_html=True)
    export_cols = ["kitchen_id","community","gas_anomaly_screening_score","screening_classification","dominant_driver","review_priority","lpg_per_meal","equipment_condition_pressure_score","supply_pressure_score","usage_signal_score"]
    report = view[export_cols].sort_values("gas_anomaly_screening_score", ascending=False).copy()
    st.dataframe(report.head(20), use_container_width=True, hide_index=True)
    report_md = "# Community Kitchen Gas-Consumption Anomaly Monitor\n\n" + "## Screening overview\n\n" + markdown_table(report, 15)
    st.download_button("Download report CSV", report.to_csv(index=False).encode(), "community_kitchen_gas_screening.csv", "text/csv")
    st.download_button("Download Markdown report", report_md.encode(), "community_kitchen_gas_screening_report.md", "text/markdown")
    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.markdown("<div class='section'><h3>Data Explorer</h3>", unsafe_allow_html=True)
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.download_button("Download filtered dataset", view.to_csv(index=False).encode(), "filtered_kitchen_gas_data.csv", "text/csv")
    st.markdown("<div class='note'><b>Local-first note:</b> all uploaded and bundled data is processed inside this application session. No external API is required by the project.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='small' style='margin-top:18px'>Synthetic demonstration data • Screening only • Review operational evidence with qualified safety, facilities, and maintenance personnel before acting.</div>", unsafe_allow_html=True)
