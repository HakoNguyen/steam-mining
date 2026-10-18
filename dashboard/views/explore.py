import streamlit as st

from lib import config, metabase
from lib.i18n import t
from lib.theme import palette

st.title(t("nav_explore"))
st.caption(t("ex_caption"))

if not config.METABASE_EMBED_SECRET:
    st.error(t("ex_missing"))
    st.stop()

try:
    url = metabase.embed_url(dark=palette().mode == "dark")
    full_url = f"{config.METABASE_PUBLIC_URL}/dashboard/{metabase.dashboard_id()}"
except Exception as e:
    st.error(t("ex_error", e=e))
    st.stop()

st.link_button(t("ex_open"), full_url, icon=":material/open_in_new:")
st.iframe(url, height=2000)
