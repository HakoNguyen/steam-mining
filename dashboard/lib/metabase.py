"""Lấy số liệu từ Metabase: Streamlit không đọc thẳng database, mà chạy các question trong
collection "Steam DWH / Streamlit" (tạo bởi scripts/metabase_dashboard.py)."""
import time

import jwt
import pandas as pd
import requests
import streamlit as st

from lib import config


def _session():
    s = requests.Session()
    s.headers["x-api-key"] = config.METABASE_API_KEY or ""
    return s


def _get(path, **params):
    r = _session().get(f"{config.METABASE_URL}/api{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=3600, show_spinner=False)
def card_ids():
    """{tên question: id} trong collection Streamlit."""
    coll = next(c for c in _get("/collection") if c["name"] == config.STREAMLIT_COLLECTION)
    items = _get(f"/collection/{coll['id']}/items", models="card")["data"]
    return {it["name"]: it["id"] for it in items}


@st.cache_data(ttl=600, show_spinner=False)
def run(name):
    """Chạy question theo tên, trả DataFrame. Lưu đệm 10 phút."""
    ids = card_ids()
    if name not in ids:  # question mới tạo sau lần đọc danh sách gần nhất: đọc lại thay vì chờ hết hạn 1 giờ
        card_ids.clear()
        ids = card_ids()
    cid = ids[name]
    r = _session().post(f"{config.METABASE_URL}/api/card/{cid}/query/json", timeout=90)
    r.raise_for_status()
    return pd.DataFrame(r.json())


@st.cache_data(ttl=3600, show_spinner=False)
def dashboard_id():
    hits = _get("/search", q=config.DASHBOARD_NAME, models="dashboard")["data"]
    return next(h["id"] for h in hits if h["name"] == config.DASHBOARD_NAME)


def embed_url(dark):
    """URL nhúng dashboard (static embedding, token JWT còn hạn 1-2 giờ).
    Hạn token làm tròn theo giờ để URL giữ nguyên giữa các lần chạy lại trang; nếu URL đổi mỗi lần,
    khung Metabase sẽ tải lại từ đầu mỗi khi người xem đổi ngôn ngữ hay bấm bất cứ thứ gì."""
    exp = (int(time.time()) // 3600 + 2) * 3600
    token = jwt.encode(
        {"resource": {"dashboard": dashboard_id()}, "params": {}, "exp": exp},
        config.METABASE_EMBED_SECRET, algorithm="HS256")
    theme = "&theme=night" if dark else ""
    return f"{config.METABASE_PUBLIC_URL}/embed/dashboard/{token}#bordered=false&titled=false{theme}"


def available():
    try:
        card_ids()
        return True
    except Exception:
        return False
