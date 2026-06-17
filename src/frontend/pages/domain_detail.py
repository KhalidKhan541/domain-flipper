import asyncio

import streamlit as st

from src.analyzers.broker import BrokerAnalyzer
from src.analyzers.commercial import CommercialAnalyzer
from src.analyzers.history import HistoryAnalyzer
from src.analyzers.seo import SEOAnalyzer
from src.checkers.rdap_checker import RDAPChecker
from src.frontend.db import get_domain_detail
from src.outreach.commission_agreement import CommissionAgreementGenerator
from src.outreach.template_generator import TemplateGenerator

GRADE_COLORS = {
    "A+": "green",
    "A": "blue",
    "B": "gold",
    "C": "orange",
    "Avoid": "red",
}


async def _load_domain_data(domain_name: str) -> dict | None:
    data = await get_domain_detail(domain_name)
    if data is None:
        return None

    seo = await SEOAnalyzer().analyze(domain_name, data)
    history = await HistoryAnalyzer().analyze(domain_name)
    commercial = await CommercialAnalyzer().analyze(domain_name)
    broker = await BrokerAnalyzer().analyze(domain_name)

    return {
        "domain": data,
        "seo": seo,
        "history": history,
        "commercial": commercial,
        "broker": broker,
    }


def _grade_badge_html(grade: str | None) -> str:
    grade = grade or "N/A"
    color = GRADE_COLORS.get(grade, "gray")
    return f'<span style="background:{color};color:white;padding:2px 14px;border-radius:12px;font-weight:700;font-size:1.1rem">{grade}</span>'


def _broker_score_color(score: float | None) -> str:
    if score is None:
        return "gray"
    if score >= 80:
        return "green"
    if score >= 60:
        return "blue"
    if score >= 40:
        return "gold"
    return "red"


def render():
    if "domain_search" not in st.session_state:
        st.session_state.domain_search = ""

    if "selected_domain" in st.session_state and st.session_state.selected_domain:
        st.session_state.domain_search = st.session_state.selected_domain
        del st.session_state.selected_domain

    domain_name = st.text_input(
        "Domain",
        placeholder="example.com",
        key="domain_search",
        label_visibility="collapsed",
    )

    if not domain_name:
        st.info(
            "Enter a domain name above to see its full analysis, "
            "or click a domain from the Discovery page."
        )
        return

    domain_name = domain_name.strip().lower()

    with st.spinner(f"Loading data for {domain_name}..."):
        result = asyncio.run(_load_domain_data(domain_name))

    if result is None:
        st.error(f"No data found for **{domain_name}**. Try running discovery first.")
        return

    d = result["domain"]
    seo = result["seo"]
    history = result["history"]
    commercial = result["commercial"]
    broker = result["broker"]

    grade = d.get("opportunity_grade") or broker.get("broker_grade")
    badge = _grade_badge_html(grade)

    st.markdown(
        f"# 🌐 {domain_name}&nbsp;&nbsp;{badge}",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        price = d.get("price")
        st.metric("Price", f"${price:,.0f}" if price is not None else "N/A")
    with col2:
        st.metric("DR", seo.get("dr", "N/A"))
    with col3:
        st.metric("Domain Age", f"{seo.get('domain_age', '?')}y")
    with col4:
        ev = broker.get("estimated_value") or 0
        st.metric("Est. Value", f"${ev:,}" if ev else "N/A")
    with col5:
        comm = broker.get("commission") or {}
        ca = comm.get("amount") or 0
        st.metric("Commission", f"${ca:,}" if ca else "N/A")
    with col6:
        fs = d.get("final_score")
        st.metric("Final Score", f"{fs:.0f}" if fs is not None else "N/A")

    st.divider()

    tab_seo, tab_history, tab_commercial = st.tabs(
        ["🔍 SEO Analysis", "📜 History & Trust", "💰 Commercial"]
    )

    with tab_seo:
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            st.metric("Domain Rating (DR)", seo.get("dr", "N/A"))
        with sc2:
            st.metric("Referring Domains", seo.get("referring_domains", "N/A"))
        with sc3:
            st.metric("Domain Age", f"{seo.get('domain_age', '?')} years")
        with sc4:
            st.metric("SEO Score", f"{seo.get('seo_score', 0):.1f}" if seo.get("seo_score") else "N/A")

    with tab_history:
        has_threat = (
            history.get("has_adult_history")
            or history.get("has_gambling_history")
            or history.get("has_pharma_history")
            or history.get("has_malware_history")
        )
        hc1, hc2, hc3, hc4 = st.columns(4)
        with hc1:
            st.metric("Cleanliness", f"{history.get('cleanliness_score', 0):.0f}%")
        with hc2:
            st.metric("Trust Score", f"{history.get('trust_score', 0):.0f}%")
        with hc3:
            snapshots = history.get("wayback_snapshots", 0)
            st.metric("Wayback Snapshots", snapshots if snapshots else "N/A")
        with hc4:
            st.metric("Has Threats", "⚠️ Yes" if has_threat else "✅ No")

    with tab_commercial:
        cc1, cc2, cc3, cc4, cc5 = st.columns(5)
        with cc1:
            st.metric("Category", commercial.get("category", "general").title())
        with cc2:
            st.metric("Commercial Score", f"{commercial.get('commercial_score', 0):.1f}")
        with cc3:
            st.metric("Brandability", f"{commercial.get('brandability', 0):.0f}%")
        with cc4:
            st.metric("Keyword Value", f"{commercial.get('keyword_value', 0):.0f}%")
        with cc5:
            st.metric("Memorability", f"{commercial.get('memorability', 0):.0f}%")

    st.divider()

    st.subheader("📊 Broker Analysis")
    broker_score = broker.get("broker_score", 0)
    bc1, bc2 = st.columns([1, 2])
    with bc1:
        score_val = broker_score / 100.0 if broker_score else 0.0
        st.progress(score_val)
        st.markdown(
            f"<h3 style='color:{_broker_score_color(broker_score)};text-align:center'>{broker_score:.0f}/100</h3>",
            unsafe_allow_html=True,
        )
    with bc2:
        st.markdown(f"**Grade:** {broker.get('broker_grade') or 'N/A'}")
        ev = broker.get("estimated_value") or 0
        if ev:
            st.markdown(f"**Estimated Value:** ${ev:,}")
        comm = broker.get("commission") or {}
        if comm:
            st.markdown(f"**Commission Rate:** {(comm.get('rate') or 0) * 100:.0f}%")
            st.markdown(f"**Commission Amount:** ${(comm.get('amount') or 0):,}")

    marketplace = broker.get("marketplace") or {}
    if marketplace and marketplace.get("listings"):
        st.markdown("#### Marketplace Listings")
        for listing in marketplace["listings"]:
            price = marketplace.get("min_price", 0)
            st.markdown(f"- {listing}" + (f" (from ${price})" if price else ""))
    else:
        st.caption("No marketplace listings found.")

    st.divider()

    leads = broker.get("buyer_leads") or {}
    lead_list = leads.get("leads") or []
    if lead_list:
        st.subheader(f"👥 Buyer Leads ({len(lead_list)})")
        import pandas as pd
        df = pd.DataFrame(lead_list)
        st.dataframe(
            df[["company", "type", "profile", "reason"]].rename(
                columns={
                    "company": "Company",
                    "type": "Type",
                    "profile": "Profile",
                    "reason": "Reason",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.subheader("👥 Buyer Leads")
        st.caption("No buyer leads generated for this domain.")

    st.divider()

    st.subheader("⚡ Quick Actions")

    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        if st.button("📧 Generate Buyer Outreach", use_container_width=True):
            first_lead = lead_list[0] if lead_list else {}
            buyer_company = first_lead.get("company", "Potential Buyer")
            buyer_name = first_lead.get("contact_name", "Buyer")
            tg = TemplateGenerator()
            template = tg.buyer_outreach(
                domain=domain_name,
                buyer_company=buyer_company,
                buyer_name=buyer_name,
                estimated_value=broker.get("estimated_value") or 1000,
                niche=commercial.get("category", "general"),
            )
            with st.expander("📧 Outreach Template", expanded=True):
                st.text_input("Subject", value=template["subject"], key="outreach_subject")
                st.text_area("Body", value=template["body"], height=250, key="outreach_body")

    with qc2:
        if st.button("📄 Generate Commission Agreement", use_container_width=True):
            first_lead = lead_list[0] if lead_list else {}
            buyer_company = first_lead.get("company", "Buyer Company")
            buyer_name = first_lead.get("contact_name", "Buyer")
            ev = broker.get("estimated_value") or 1000
            comm = broker.get("commission") or {}
            cr = comm.get("rate") or 0.15
            ca = comm.get("amount") or int(ev * cr)
            generator = CommissionAgreementGenerator()
            html = asyncio.run(
                generator.generate(
                    domain=domain_name,
                    buyer_name=buyer_name,
                    buyer_company=buyer_company,
                    seller_name="Seller",
                    seller_company="Domain Owner",
                    commission_amount=ca,
                    commission_rate=cr,
                    estimated_value=ev,
                )
            )
            with st.expander("📄 Commission Agreement Preview", expanded=True):
                st.markdown(html, unsafe_allow_html=True)

    with qc3:
        if st.button("🔍 Check Availability via RDAP", use_container_width=True):
            checker = RDAPChecker()
            rdap_result = asyncio.run(checker.check(domain_name))
            available = rdap_result.get("available")
            method = rdap_result.get("method", "unknown")
            confidence = rdap_result.get("confidence", "low")
            status = "✅ Available" if available else "❌ Registered"
            with st.expander("🔍 RDAP Result", expanded=True):
                st.markdown(f"**Status:** {status}")
                st.markdown(f"**Method:** {method}")
                st.markdown(f"**Confidence:** {confidence}")
