import asyncio

import streamlit as st

from src.frontend.db import get_deals, get_all_purchases
from src.outreach.commission_agreement import CommissionAgreementGenerator
from src.outreach.tracker import OutreachTracker


def render():
    st.title("💰 Deals & Commission Agreements")

    tab1, tab2 = st.tabs(["Active Deals", "New Agreement"])

    with tab1:
        _render_active_deals()

    with tab2:
        _render_new_agreement()

    with st.expander("📦 Purchase History"):
        _render_purchase_history()


def _render_active_deals():
    deals = asyncio.run(get_deals())

    total = len(deals)
    total_commission = sum(d.get("commission_amount") or 0 for d in deals)
    avg_rate = (
        (sum(d.get("commission_rate") or 0 for d in deals) / total)
        if total
        else 0.0
    )
    signed = sum(1 for d in deals if d.get("status") == "signed")
    paid = sum(1 for d in deals if d.get("status") == "paid")

    cols = st.columns(5)
    cols[0].metric("Total Deals", total)
    cols[1].metric("Total Commission", f"${total_commission:,.0f}")
    cols[2].metric("Avg Commission Rate", f"{avg_rate:.0%}")
    cols[3].metric("Signed", signed)
    cols[4].metric("Paid", paid)

    st.markdown("---")

    status_colors = {
        "pending": "orange",
        "signed": "blue",
        "paid": "green",
        "cancelled": "red",
        "draft": "gray",
    }

    for deal in deals:
        status = (deal.get("status") or "draft").lower()
        color = status_colors.get(status, "gray")
        label = f":{color}[{status}]"

        with st.container(border=True):
            cols = st.columns([2, 2, 2, 1.5, 1, 1.5, 1.5, 1.5])
            cols[0].markdown(f"**ID** {deal.get('id')}")
            cols[1].markdown(f"**Domain** {deal.get('domain_name', '')}")
            cols[2].markdown(f"**Buyer** {deal.get('buyer_name', '')}")
            cols[3].markdown(f"**Seller** {deal.get('seller_name', '')}")
            cols[4].markdown(
                f"**Comm.** ${deal.get('commission_amount') or 0:,.0f}"
            )
            cols[5].markdown(
                f"**Rate** {(deal.get('commission_rate') or 0) * 100:.0f}%"
            )
            cols[6].markdown(f"**Status** {label}")
            cols[7].markdown(
                f"**Created** {str(deal.get('created_at', ''))[:10]}"
            )

            with st.expander("View Details"):
                st.json(deal)
                if deal.get("agreement_path"):
                    st.markdown(f"**Agreement file:** `{deal['agreement_path']}`")

            new_status = st.selectbox(
                "Update status",
                ["", "draft", "pending", "signed", "paid", "cancelled"],
                key=f"status_{deal['id']}",
                label_visibility="collapsed",
                placeholder="Update status...",
            )
            if st.button("Apply", key=f"apply_{deal['id']}"):
                if new_status:
                    asyncio.run(_update_deal_status(deal["id"], new_status))
                    st.rerun()


async def _update_deal_status(deal_id: int, new_status: str) -> None:
    tracker = OutreachTracker()
    await tracker.init_db()
    conn = await tracker._connect()
    await conn.execute(
        "UPDATE commission_agreements SET status = ? WHERE id = ?",
        (new_status, deal_id),
    )
    await conn.commit()


def _render_new_agreement():
    with st.form("new_agreement_form", clear_on_submit=True):
        domain = st.text_input("Domain Name", placeholder="example.com")
        col1, col2 = st.columns(2)
        buyer_name = col1.text_input("Buyer Name")
        buyer_company = col2.text_input("Buyer Company")
        col3, col4 = st.columns(2)
        seller_name = col3.text_input("Seller Name")
        seller_company = col4.text_input("Seller Company")
        estimated_value = st.number_input(
            "Estimated Value ($)",
            min_value=0,
            step=100,
            value=0,
        )
        commission_rate = st.slider(
            "Commission Rate",
            min_value=5,
            max_value=30,
            value=15,
            format="%%d %%",
        ) / 100.0

        submitted = st.form_submit_button("📄 Generate Agreement", type="primary")

    if submitted:
        if not domain:
            st.error("Domain name is required.")
            return
        if not buyer_name or not seller_name:
            st.error("Buyer and seller names are required.")
            return

        commission_amount = int(estimated_value * commission_rate)

        with st.spinner("Generating commission agreement..."):
            gen = CommissionAgreementGenerator()
            html = asyncio.run(
                gen.generate(
                    domain=domain,
                    buyer_name=buyer_name,
                    buyer_company=buyer_company,
                    seller_name=seller_name,
                    seller_company=seller_company,
                    commission_amount=commission_amount,
                    commission_rate=commission_rate,
                    estimated_value=int(estimated_value),
                )
            )
            file_path = asyncio.run(gen.save(html, domain))

            tracker = OutreachTracker()
            asyncio.run(tracker.init_db())
            asyncio.run(
                tracker.save_agreement(
                    domain_name=domain,
                    buyer_name=buyer_name,
                    buyer_company=buyer_company,
                    seller_name=seller_name,
                    seller_company=seller_company,
                    commission_amount=float(commission_amount),
                    commission_rate=commission_rate,
                    estimated_value=float(estimated_value),
                    agreement_path=str(file_path),
                )
            )

        st.success(
            f"✅ Agreement generated and saved to `{file_path}`"
        )

        st.subheader("Preview")
        st.components.v1.html(html, height=600, scrolling=True)

        with open(file_path, "r", encoding="utf-8") as f:
            st.download_button(
                label="⬇️ Download HTML Agreement",
                data=f.read(),
                file_name=file_path.name,
                mime="text/html",
            )


def _render_purchase_history():
    purchases = asyncio.run(get_all_purchases())

    if not purchases:
        st.info("No purchases recorded yet.")
        return

    data = []
    for p in purchases:
        data.append(
            {
                "Domain": p.get("domain_name", ""),
                "Purchase Price": p.get("purchase_price"),
                "Purchase Date": str(p.get("purchase_date", ""))[:10],
                "Sale Price": p.get("sale_price"),
                "Sale Date": str(p.get("sale_date", ""))[:10],
                "ROI": f"{p.get('roi', 0) * 100:.1f}%"
                if p.get("roi") is not None
                else "",
                "Notes": p.get("notes", ""),
            }
        )

    st.dataframe(data, use_container_width=True, hide_index=True)
