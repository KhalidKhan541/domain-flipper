import asyncio

import streamlit as st

from src.frontend.db import get_dashboard_stats, get_leads, get_recent_runs, get_top_domains


def _grade_color(grade: str) -> str:
    color = {
        "A+": "green",
        "A": "blue",
        "B": "gold",
        "C": "orange",
        "Avoid": "red",
    }.get(grade, "gray")
    return f'<span style="color:{color};font-weight:bold">{grade}</span>'


def render():
    stats = asyncio.run(get_dashboard_stats()) or {}
    top_domains = asyncio.run(get_top_domains(10)) or []
    recent_runs = asyncio.run(get_recent_runs(5)) or []

    st.title("📊 Domain Broker Dashboard")

    # ---- Key Metrics Row ----
    top = stats.get("top_domain") or {}
    top_name = (top.get("name") or "N/A")[:20]
    if len(top.get("name") or "") > 20:
        top_name += "..."

    cols = st.columns(5)
    cols[0].metric("Domains Today", stats.get("domains_today") or 0)
    cols[1].metric("Avg Broker Score", f"{(stats.get('avg_broker_score') or 0):.1f}")
    cols[2].metric("Domains Total", stats.get("total_domains") or 0)
    cols[3].metric("Top Domain", top_name, delta=top.get("score") or 0)
    cols[4].metric("Avg Final Score", f"{(stats.get('avg_final_score') or 0):.1f}")

    # ---- Pipeline Overview ----
    st.subheader("Pipeline Overview")
    hot_leads = sum(1 for d in top_domains if d.get("opportunity_grade") == "Hot Lead")

    pipe_left, pipe_right = st.columns(2)
    with pipe_left:
        pcols = st.columns(4)
        pcols[0].metric("Discovered", stats.get("total_domains") or 0)
        pcols[1].metric("Analyzed", stats.get("total_domains") or 0)
        pcols[2].metric("Hot Leads", hot_leads)
        pcols[3].metric("Deals", 0)

    with pipe_right:
        st.markdown("**Recent Activity**")
        if recent_runs:
            st.dataframe(
                [
                    {
                        "Source": r.get("source", ""),
                        "Found": r.get("domains_found", 0),
                        "Status": r.get("status", ""),
                    }
                    for r in recent_runs
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No recent runs found.")

    # ---- Top Opportunities ----
    st.subheader("🏆 Top Opportunities")
    if top_domains:
        rows = []
        for d in top_domains:
            rows.append(
                {
                    "Domain": d.get("domain_name", ""),
                    "Score": d.get("final_score", 0) or 0,
                    "Grade": d.get("opportunity_grade", ""),
                    "Broker": d.get("broker_score", 0) or 0,
                    "Est. Value": d.get("estimated_value", 0) or 0,
                    "Commission": d.get("commission_amount", 0) or 0,
                    "Buyers": d.get("buyer_lead_count", 0) or 0,
                    "Source": d.get("source", ""),
                }
            )

        st.dataframe(
            rows,
            column_config={
                "Domain": st.column_config.TextColumn("Domain"),
                "Score": st.column_config.NumberColumn("Score", format="%.1f"),
                "Grade": st.column_config.TextColumn("Grade"),
                "Broker": st.column_config.ProgressColumn("Broker", min_value=0, max_value=100),
                "Est. Value": st.column_config.NumberColumn("Est. Value", format="$%d"),
                "Commission": st.column_config.NumberColumn("Commission", format="$%d"),
                "Buyers": st.column_config.NumberColumn("Buyers"),
                "Source": st.column_config.TextColumn("Source"),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            "Grades: "
            + " | ".join(
                _grade_color(g) for g in sorted(set(d.get("opportunity_grade", "") for d in top_domains if d.get("opportunity_grade")))
            ),
            unsafe_allow_html=True,
        )
    else:
        st.info("No domains found yet.")

    # ---- Grade Distribution ----
    st.subheader("Grade Distribution")
    g_left, g_right = st.columns(2)
    with g_left:
        by_grade = stats.get("domains_by_grade") or {}
        if by_grade:
            st.bar_chart(by_grade)
        else:
            st.info("No grade data available.")
    with g_right:
        by_source = stats.get("domains_by_source") or {}
        if by_source:
            st.bar_chart(by_source)
        else:
            st.info("No source data available.")

    # ---- Quick Actions ----
    st.subheader("⚡ Quick Actions")
    acols = st.columns(3)
    if acols[0].button("🔍 Run Discovery"):
        st.info("Go to the Discovery page to run the pipeline")
    if acols[1].button("📬 View Outreach"):
        st.info("Go to the Outreach page to manage leads")
    if acols[2].button("💰 View Deals"):
        st.info("Go to the Deals page for commission agreements")
