import asyncio
import streamlit as st
import pandas as pd

from src.coordinators.broker import BrokerCoordinator

NICHES = [
    "ai", "saas", "finance", "health", "ecommerce", "education",
    "cybersecurity", "realestate", "productivity", "legal",
]

GRADE_COLORS = {
    "Hot Lead": "background-color: #00cc66; color: white",
    "Warm": "background-color: #3399ff; color: white",
    "Lukewarm": "background-color: #ff9933; color: white",
    "Cold": "background-color: #999999; color: white",
}

GRADE_ORDER = {"Hot Lead": 0, "Warm": 1, "Lukewarm": 2, "Cold": 3}

COLUMNS = [
    "Domain", "Price", "DR", "Domain Age", "SEO Score",
    "Commercial Score", "Trust Score", "Final Score",
    "Broker Score", "Grade", "Est Value", "Commission",
    "Buyer Leads", "Source",
]


def _build_df(results: list[dict]) -> pd.DataFrame:
    rows = []
    for d in results:
        rows.append({
            "Domain": d.get("domain_name", ""),
            "Price": d.get("price", 0),
            "DR": d.get("dr", 0),
            "Domain Age": d.get("domain_age", 0),
            "SEO Score": d.get("seo_score", 0),
            "Commercial Score": d.get("commercial_score", 0),
            "Trust Score": d.get("trust_score", 0),
            "Final Score": d.get("final_score", 0),
            "Broker Score": d.get("broker_score") or 0,
            "Grade": d.get("broker_grade") or "Cold",
            "Est Value": d.get("estimated_value") or 0,
            "Commission": (d.get("commission") or {}).get("amount", 0) or 0,
            "Buyer Leads": (d.get("buyer_leads") or {}).get("total_leads", 0) or 0,
            "Source": d.get("source", ""),
            "category": d.get("category", "general"),
        })
    df = pd.DataFrame(rows)
    return df


def _color_grade(val: str) -> str:
    return GRADE_COLORS.get(val, "")


def render():
    st.title("Domain Discovery")
    st.markdown(
        "Run the full broker pipeline to discover, analyze, and score "
        "domains for brokering opportunities."
    )

    with st.expander("Discovery Controls", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            niche = st.selectbox("Niche", NICHES, index=0)
        with col2:
            max_domains = st.number_input(
                "Max Domains", min_value=1, max_value=200, value=50, step=5
            )

        min_broker_score = st.slider("Min Broker Score", 0, 100, 0)
        run_clicked = st.button("🚀 Run Discovery", type="primary", use_container_width=True)

    if run_clicked:
        st.session_state.discovery_results = None
        with st.spinner("Running broker pipeline — discovering and analyzing domains..."):
            results = asyncio.run(_run_discovery(niche, max_domains, min_broker_score))
            st.session_state.discovery_results = results
            st.rerun()

    results = st.session_state.get("discovery_results")
    if results is not None:
        _show_results(results)


async def _run_discovery(
    niche: str, max_domains: int, min_broker_score: int,
) -> list[dict]:
    coordinator = BrokerCoordinator()
    domains = await coordinator.discover(max_domains=max_domains)
    analyzed = await coordinator.analyze_all(domains)
    if min_broker_score > 0:
        analyzed = [
            d for d in analyzed
            if d.get("broker_score", 0) >= min_broker_score
        ]
    return analyzed


def _show_results(results: list[dict]) -> None:
    st.divider()
    st.subheader("Discovery Results")
    st.caption(f"{len(results)} domains found")

    df = _build_df(results)

    if df.empty:
        st.info("No domains found.")
        return

    grade_series = df["Grade"].map(GRADE_ORDER)
    best_grade = df.loc[grade_series.idxmin(), "Grade"]

    total_found = len(df)
    avg_broker_score = round(df["Broker Score"].mean(), 1)
    total_est_value = int(df["Est Value"].sum())
    total_commission = int(df["Commission"].sum())

    metric_cols = st.columns(5)
    metric_cols[0].metric("Total Found", total_found)
    metric_cols[1].metric("Avg Broker Score", avg_broker_score)
    metric_cols[2].metric("Best Grade", best_grade)
    metric_cols[3].metric("Total Est Value", f"${total_est_value:,}")
    metric_cols[4].metric("Total Commission", f"${total_commission:,}")

    display_df = df[COLUMNS].copy()

    styled = display_df.style.applymap(
        _color_grade, subset=["Grade"]
    )

    event = st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.0f"),
            "Est Value": st.column_config.NumberColumn(format="$%.0f"),
            "Commission": st.column_config.NumberColumn(format="$%.0f"),
            "DR": st.column_config.NumberColumn(format="%.0f"),
            "Domain Age": st.column_config.NumberColumn(format="%.0f"),
        },
        on_select="rerun",
        selection_mode="single-row",
        key="discovery_table",
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        selected_domain = display_df.iloc[idx]["Domain"]
        st.info(f"Selected: **{selected_domain}**")
        if st.button("View Domain Details"):
            st.session_state.selected_domain = selected_domain
            st.rerun()

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name="domain_discovery_results.csv",
        mime="text/csv",
    )

    st.subheader("Niche Distribution")
    niche_counts = df["category"].value_counts()
    if not niche_counts.empty:
        st.bar_chart(niche_counts)
    else:
        st.caption("No data available for niche distribution.")
