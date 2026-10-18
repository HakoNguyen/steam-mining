import streamlit as st

from lib import fmt, metabase
from lib.i18n import t

st.title("Steam Market Intelligence")
st.markdown(t("home_intro"))

if metabase.available():
    try:
        kpi = metabase.run("[Streamlit] KPI thị trường").iloc[0]
        ccu = metabase.run("[Streamlit] KPI CCU theo ngày").sort_values("full_date")
        a, b, c = st.columns(3)
        a.metric(t("kpi_ccu"), fmt.compact(ccu["total_peak_ccu"].iloc[-1]), border=True)
        b.metric(t("kpi_games"), fmt.num(kpi["n_games"]), border=True)
        c.metric(t("kpi_price"), fmt.vnd(kpi["median_price_vnd"]), border=True)
    except Exception:
        pass

st.subheader(t("home_start"))
cols = st.columns(3)
pages = [
    ("views/smart_dashboard.py", ":material/monitoring:", t("nav_smart"), t("home_smart_desc")),
    ("views/explore.py", ":material/travel_explore:", t("nav_explore"), t("home_explore_desc")),
    ("views/copilot.py", ":material/smart_toy:", t("nav_copilot"), t("home_copilot_desc")),
]
for col, (path, icon, title, desc) in zip(cols, pages):
    with col.container(border=True, height="stretch"):
        st.markdown(f"#### {title}")
        st.caption(desc)
        st.page_link(path, label=t("home_open", title=title), icon=icon)
