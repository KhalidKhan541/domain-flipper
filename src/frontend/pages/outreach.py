import asyncio

import pandas as pd
import streamlit as st

from src.frontend.db import get_lead, get_leads, update_lead_status
from src.outreach.template_generator import TemplateGenerator
from src.outreach.tracker import OutreachTracker

STATUS_COLORS = {
    "pending": "#808080",
    "sent": "#1E90FF",
    "replied": "#FFD700",
    "negotiating": "#FF8C00",
    "closed_won": "#32CD32",
    "closed_lost": "#FF4444",
}

STATUS_OPTIONS = ["All", "pending", "sent", "replied", "negotiating", "closed_won", "closed_lost"]
TYPE_OPTIONS = ["All", "buyer", "seller"]


def _build_df(leads: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(leads)
    if df.empty:
        return df
    cols = ["id", "domain_name", "lead_type", "company", "contact_name", "contact_email", "status", "created_at"]
    present = [c for c in cols if c in df.columns]
    return df[present].copy()


def _color_status(val: str) -> str:
    color = STATUS_COLORS.get(val, "#808080")
    return f"color: {color}; font-weight: 600;"


def _stats_cards(leads: list[dict]) -> None:
    total = len(leads)
    counts: dict[str, int] = {}
    for l in leads:
        s = l.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1

    cards = [
        ("Total Leads", str(total), "#1E1E2E"),
        ("Pending", str(counts.get("pending", 0)), "#808080"),
        ("Sent", str(counts.get("sent", 0)), "#1E90FF"),
        ("Replied", str(counts.get("replied", 0)), "#FFD700"),
        ("Negotiating", str(counts.get("negotiating", 0)), "#FF8C00"),
        ("Closed Won", str(counts.get("closed_won", 0)), "#32CD32"),
        ("Closed Lost", str(counts.get("closed_lost", 0)), "#FF4444"),
    ]

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    for col, (label, value, bg) in zip(
        [c1, c2, c3, c4, c5, c6, c7], cards
    ):
        col.markdown(
            f"<div style='background:{bg}; padding:8px; border-radius:8px; text-align:center; color:white;'>"
            f"<div style='font-size:12px; opacity:0.8;'>{label}</div>"
            f"<div style='font-size:22px; font-weight:700;'>{value}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_filters() -> tuple[str, str, str]:
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        status = st.selectbox("Status", STATUS_OPTIONS, key="outreach_status_filter")
    with col2:
        lead_type = st.selectbox("Type", TYPE_OPTIONS, key="outreach_type_filter")
    with col3:
        search = st.text_input("Search domain", placeholder="domain name...", key="outreach_search")
    return status, lead_type, search.strip().lower()


def _render_lead_detail(lead: dict) -> None:
    st.markdown("---")
    st.subheader(f"📄 Lead #{lead.get('id', '?')} — {lead.get('domain_name', '')}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Domain:** {lead.get('domain_name', '—')}")
        st.markdown(f"**Type:** {lead.get('lead_type', '—')}")
        st.markdown(f"**Company:** {lead.get('company', '—')}")
        st.markdown(f"**Contact Name:** {lead.get('contact_name', '—')}")
        st.markdown(f"**Title:** {lead.get('contact_title', '—')}")
    with col2:
        st.markdown(f"**Email:** {lead.get('contact_email', '—')}")
        st.markdown(f"**LinkedIn:** {lead.get('contact_linkedin', '—')}")
        st.markdown(f"**Status:** {lead.get('status', '—')}")
        st.markdown(f"**Notes:** {lead.get('notes', '—') or '—'}")

    st.markdown("#### Update Lead")
    new_status = st.selectbox(
        "Status",
        [s for s in STATUS_OPTIONS if s != "All"],
        index=([s for s in STATUS_OPTIONS if s != "All"].index(lead.get("status", "pending")) if lead.get("status") in [s for s in STATUS_OPTIONS if s != "All"] else 0),
        key="lead_detail_status",
    )
    new_notes = st.text_area("Notes", value=lead.get("notes", "") or "", key="lead_detail_notes")

    if st.button("Update", type="primary", key="update_lead_btn"):
        lead_id = lead.get("id")
        if lead_id is not None:
            asyncio.run(update_lead_status(lead_id, new_status, new_notes))
            st.success(f"Lead #{lead_id} updated.")
        st.rerun()

    with st.expander("📧 Template Preview"):
        tg = TemplateGenerator()
        domain = lead.get("domain_name", "")
        lead_type = lead.get("lead_type", "")
        company = lead.get("company", "")
        contact_name = lead.get("contact_name", "")
        estimated_value = lead.get("estimated_value", 5000)
        niche = lead.get("niche", "technology")

        if lead_type == "buyer":
            tmpl = tg.buyer_outreach(domain, company, contact_name, estimated_value, niche)
        elif lead_type == "seller":
            tmpl = tg.seller_outreach(domain, contact_name, estimated_value)
        else:
            tmpl = {"subject": "—", "body": "No template available for this lead type."}

        st.markdown(f"**Subject:** {tmpl['subject']}")
        st.text_area("Body", tmpl["body"], height=200, key="template_preview")

    if st.button("✉️ Send Email", key="send_email_btn"):
        st.info(
            f"📧 Email would be sent to {lead.get('contact_email', '—')} "
            f"regarding {lead.get('domain_name', '—')}. "
            "SMTP sending depends on email configuration."
        )


def render() -> None:
    st.title("📬 Outreach Dashboard")

    all_leads = asyncio.run(get_leads())
    _stats_cards(all_leads)

    status_filter, type_filter, search = _render_filters()

    status_param = None if status_filter == "All" else status_filter
    type_param = None if type_filter == "All" else type_filter

    leads = asyncio.run(get_leads(status=status_param, lead_type=type_param))

    if search:
        leads = [l for l in leads if search in l.get("domain_name", "").lower()]

    df = _build_df(leads)
    if df.empty:
        st.info("No leads match the current filters.")
        return

    styled = df.style.map(_color_status, subset=["status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    lead_ids = [l.get("id") for l in leads if l.get("id") is not None]
    selected_id = st.selectbox(
        "Select Lead ID to view details",
        options=lead_ids,
        format_func=lambda x: f"#{x} — {next((l.get('domain_name', '') for l in leads if l.get('id') == x), '')}",
        key="lead_selector",
    )

    if selected_id:
        st.session_state["selected_lead_id"] = selected_id

    if "selected_lead_id" in st.session_state:
        lead = asyncio.run(get_lead(st.session_state["selected_lead_id"]))
        if lead:
            _render_lead_detail(lead)

    st.markdown("---")
    st.subheader("⚡ Bulk Actions")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Mark Selected as Sent", key="bulk_mark_sent"):
            for l in leads:
                if l.get("status") == "pending" and l.get("id") is not None:
                    asyncio.run(update_lead_status(l["id"], "sent", None))
            st.success("All pending leads marked as sent.")
            st.rerun()

    with col_b2:
        sent_leads = [l for l in leads if l.get("status") == "sent"]
        if st.button("Generate Follow-up", key="bulk_followup"):
            tg = TemplateGenerator()
            for l in sent_leads:
                lead_id = l.get("id")
                if lead_id is None:
                    continue
                tmpl = tg.follow_up(
                    previous_subject=l.get("template_subject", "Previous email"),
                    domain=l.get("domain_name", ""),
                    buyer_company=l.get("company", ""),
                    attempt=1,
                )
                asyncio.run(
                    update_lead_status(
                        lead_id,
                        "sent",
                        f"Follow-up generated — subject: {tmpl['subject']}",
                    )
                )
            st.success(f"Follow-ups generated for {len(sent_leads)} sent lead(s).")
            st.rerun()
