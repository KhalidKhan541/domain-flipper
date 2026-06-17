import asyncio
import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.frontend.pages import dashboard, deals, discovery, domain_detail, outreach

st.set_page_config(
    page_title="Domain Flipper",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "📊 Dashboard": dashboard,
    "🔍 Discovery": discovery,
    "🌐 Domain Details": domain_detail,
    "📬 Outreach": outreach,
    "💰 Deals": deals,
    "⚙️ Settings": None,
}


def show_settings():
    st.title("⚙️ Settings")
    st.markdown("Configure your Domain Flipper preferences.")
    st.divider()
    st.subheader("General")
    st.text_input("API Base URL", value="http://localhost:8000")
    st.subheader("Notifications")
    st.checkbox("Enable email notifications", value=True)
    st.checkbox("Enable desktop notifications", value=False)
    st.subheader("Theme")
    st.selectbox("Color theme", ["Dark", "Light"], index=0)


def main():
    st.sidebar.markdown(
        f"<h2 style='text-align: center;'>🔄 Domain Flipper</h2>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    page_names = list(PAGES.keys())
    selected = st.sidebar.selectbox("Navigate", page_names, label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.markdown(f"**Version:** 1.0.0")
    st.sidebar.markdown(f"**Last run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    module = PAGES[selected]
    if module is not None:
        module.render()
    else:
        show_settings()


if __name__ == "__main__":
    main()
