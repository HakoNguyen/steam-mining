r"""Steam Market Intelligence: Smart Dashboard + AI Copilot.

Chạy (từ thư mục dashboard/, đã bật .venv):  python -m streamlit run app.py   ->  http://localhost:8501
(Không gọi streamlit.exe trực tiếp: Windows Application Control có thể chặn file .exe không ký số trong .venv.)
"""
import sys
from pathlib import Path

import streamlit as st


@st.cache_resource
def _lib_state():
    return {}


def _fresh_lib():
    """Sửa code lúc server đang chạy: Streamlit tự nạp lại từng file một nên có lúc trang mới chạy cùng
    module cũ (vd. KeyError vì i18n.py chưa được nạp lại). Thấy file nào trong lib/ đổi thì bỏ hết các
    module lib.* để lần import dưới đây nạp lại đồng loạt."""
    stamp = max(f.stat().st_mtime_ns for f in (Path(__file__).parent / "lib").glob("*.py"))
    state = _lib_state()
    if state.get("stamp") != stamp:
        for name in [m for m in sys.modules if m == "lib" or m.startswith("lib.")]:
            del sys.modules[name]
        state["stamp"] = stamp


_fresh_lib()

from lib import i18n  # noqa: E402  (phải sau _fresh_lib)
from lib.i18n import t
from lib.theme import inject_css

st.set_page_config(page_title="Steam Market Intelligence", page_icon=":material/sports_esports:", layout="wide")
inject_css()
i18n.selector()  # trước navigation để tên trang đổi theo ngôn ngữ

nav = st.navigation({
    "": [st.Page("views/home.py", title=t("nav_home"), icon=":material/home:", url_path="home", default=True)],
    t("nav_analysis"): [
        st.Page("views/smart_dashboard.py", title=t("nav_smart"), icon=":material/monitoring:", url_path="smart"),
        st.Page("views/explore.py", title=t("nav_explore"), icon=":material/travel_explore:", url_path="explore"),
    ],
    t("nav_ai"): [st.Page("views/copilot.py", title=t("nav_copilot"), icon=":material/smart_toy:", url_path="copilot")],
})
nav.run()
