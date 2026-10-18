import streamlit as st

from lib.i18n import t

st.title(t("nav_copilot"))
st.caption(t("cp_caption"))

st.info(t("cp_info"), icon=":material/construction:")
