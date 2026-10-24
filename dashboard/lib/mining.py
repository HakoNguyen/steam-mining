"""Kết quả khai phá dữ liệu cho trang "Khai phá dữ liệu".

- Luật Apriori và phân cụm K-Means: schema mining trong warehouse, đọc qua Metabase như các trang khác
  (các question "[Streamlit] Mining ..." trong scripts/metabase_dashboard.py).
- Chỉ số mô hình, cây CART, phân loại review, chủ đề NMF: file trong mining/outputs/ do các script trong mining/
  ghi ra (chạy tay hằng tuần, xem README). Bộ đệm gắn với thời điểm sửa file nên chạy lại script là trang tự cập nhật.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).resolve().parents[2] / "mining" / "outputs"


def _stamp(name):
    p = OUT / name
    return p.stat().st_mtime_ns if p.exists() else None


@st.cache_data(show_spinner=False)
def _read_json(name, stamp):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def _read_csv(name, stamp):
    return pd.read_csv(OUT / name, encoding="utf-8-sig")


@st.cache_data(show_spinner=False)
def _read_text(name, stamp):
    return (OUT / name).read_text(encoding="utf-8")


def load_json(name):
    s = _stamp(name)
    return _read_json(name, s) if s else None


def load_csv(name):
    s = _stamp(name)
    return _read_csv(name, s) if s else None


def load_text(name):
    s = _stamp(name)
    return _read_text(name, s) if s else None


@st.cache_data(show_spinner=False)
def _cart_importance(stamp):
    import joblib  # chỉ cần khi có file mô hình
    bundle = joblib.load(OUT / "cart.joblib")
    s = pd.Series(bundle["model"].feature_importances_, index=bundle["features"])
    return s[s > 0].sort_values(ascending=False).rename("importance").rename_axis("feature").reset_index()


def cart_importance():
    """Mức quan trọng đặc trưng của cây CART (đọc lại từ mô hình đã lưu, file chỉ có ảnh PNG)."""
    s = _stamp("cart.joblib")
    return _cart_importance(s) if s else None


@st.cache_data(show_spinner=False)
def _review_terms(stamp, n):
    import joblib
    pipe = joblib.load(OUT / "review_clf.joblib")
    tfidf, model = pipe.steps[0][1], pipe.steps[-1][1]
    if not hasattr(model, "coef_"):  # mô hình tốt nhất là Naive Bayes: không có hệ số dấu +/- để vẽ
        return None
    coef = pd.Series(model.coef_[0], index=tfidf.get_feature_names_out()).sort_values()
    return pd.concat([coef.head(n), coef.tail(n)]).rename("coef").rename_axis("term").reset_index()


def review_terms(n=12):
    """Từ/cụm từ đẩy mạnh nhất về chê (hệ số âm) và khen (hệ số dương) của Logistic Regression."""
    s = _stamp("review_clf.joblib")
    return _review_terms(s, n) if s else None


def updated_at():
    """Thời điểm chạy script mining gần nhất (file kết quả mới nhất)."""
    files = list(OUT.glob("*")) if OUT.exists() else []
    return datetime.fromtimestamp(max(f.stat().st_mtime for f in files)) if files else None
