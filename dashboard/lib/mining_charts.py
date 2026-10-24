"""Biểu đồ Plotly cho trang Khai phá dữ liệu (cùng bảng màu và style() với Smart Dashboard)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from lib import fmt
from lib.charts import _log_ticks
from lib.i18n import t
from lib.theme import style


def _bar_h(fig, p, height):
    style(fig, p, height=height)
    fig.update_yaxes(showgrid=False, tickfont=dict(color=p.ink2, size=12))
    return fig


# ------------------------------------------------------------------ Apriori

def rules_confidence(df, base_rate, p):
    """Mỗi combo tag -> % game được khen cao; vạch dọc = tỷ lệ chung của toàn tập (luật có ích khi vượt vạch)."""
    d = df.sort_values("confidence")
    conf = d["confidence"] * 100
    fig = go.Figure(go.Bar(
        x=conf, y=d["combo"], orientation="h", marker=dict(color=p.series[0]),
        text=[f"{fmt.pct(c)} · ×{fmt.num(l, 2)}" for c, l in zip(conf, d["lift"])],
        textposition="outside", cliponaxis=False, textfont=dict(color=p.ink2, size=11),
        customdata=np.stack([d["n_games_with_combo"], d["n_high_positive"], d["support"] * 100, d["lift"]], axis=-1),
        hovertemplate=f"<b>%{{y}}</b><br>{t('mn_h_conf')}: %{{x:.1f}}%<br>{t('mn_h_lift')}: ×%{{customdata[3]:.2f}}"
                      f"<br>{t('mn_h_n_combo')}: %{{customdata[0]:,.0f}}<br>{t('mn_h_n_hp')}: %{{customdata[1]:,.0f}}"
                      f"<br>{t('mn_h_support')}: %{{customdata[2]:.1f}}%<extra></extra>"))
    _bar_h(fig, p, height=max(360, 26 * len(d) + 70))
    fig.update_xaxes(showticklabels=False, showline=False, range=[0, conf.max() * 1.28])
    fig.add_vline(x=base_rate * 100, line=dict(color=p.muted, width=1.5, dash="dot"))
    fig.add_annotation(x=base_rate * 100, y=1, yref="paper", yanchor="bottom", showarrow=False,
                       text=t("mn_base_rate_line", v=fmt.pct(base_rate * 100)), font=dict(color=p.muted, size=11))
    fig.update_layout(margin=dict(t=28))
    return fig


# ------------------------------------------------------------------ K-Means

def _k_line(values, chosen, p, ytitle, fmt_y):
    ks = sorted(values, key=int)
    xs, ys = [int(k) for k in ks], [values[k] for k in ks]
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", line=dict(color=p.series[0], width=2),
                               marker=dict(size=7, color=p.series[0]),
                               hovertemplate="k = %{x}<br>" + ytitle + ": %{y" + fmt_y + "}<extra></extra>"))
    cy = values[str(chosen)]
    fig.add_trace(go.Scatter(x=[chosen], y=[cy], mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(size=14, color=p.series[0], line=dict(color=p.surface, width=3))))
    fig.add_annotation(x=chosen, y=cy, text=t("mn_chosen_k", k=chosen), showarrow=False, xanchor="left",
                       xshift=12, yshift=12, font=dict(color=p.ink2, size=11))
    style(fig, p, height=260)
    fig.update_xaxes(title_text=t("mn_ax_k"), dtick=1)
    fig.update_yaxes(title_text=ytitle)
    return fig


def silhouette(metrics, p):
    return _k_line(metrics["silhouette"], metrics["best_k"], p, t("mn_ax_silhouette"), ":.3f")


def inertia(metrics, p):
    return _k_line(metrics["inertia"], metrics["best_k"], p, t("mn_ax_inertia"), ":,.0f")


def clusters_scatter(df, p, names):
    """CCU trung bình (thang log) và tỷ lệ khen của từng game, màu theo phân khúc (màu gắn theo cụm, không theo thứ hạng)."""
    fig = go.Figure()
    for cid in sorted(df["cluster_id"].unique()):
        g = df[df["cluster_id"] == cid]
        price = [t("free") if f else fmt.vnd(v) for v, f in zip(g["price_vnd"], g["is_free"])]
        fig.add_trace(go.Scatter(
            x=g["avg_ccu"].clip(lower=1), y=g["positive_ratio"] * 100, mode="markers", name=names[cid],
            marker=dict(size=6, color=p.series[int(cid) % len(p.series)], opacity=0.55, line=dict(width=0)),
            customdata=np.stack([g["game_title"], price, [fmt.compact(v) for v in g["owners_mid"]]], axis=-1),
            hovertemplate=f"<b>%{{customdata[0]}}</b><br>{t('h_price')}: %{{customdata[1]}}"
                          f"<br>CCU TB: %{{x:,.0f}}<br>{t('h_pos_reviews')}: %{{y:.1f}}%"
                          f"<br>{t('h_owners')}: %{{customdata[2]}}<extra>{names[cid]}</extra>"))
    style(fig, p, height=460, legend=True)
    x = df["avg_ccu"].clip(lower=1)
    fig.update_xaxes(type="log", showgrid=True, title_text=t("mn_ax_ccu_log"), tickvals=_log_ticks(x.min(), x.max()),
                     tickformat="~s")
    fig.update_yaxes(title_text=t("ax_pos_reviews"), ticksuffix="%")
    return fig


# ------------------------------------------------------------------ CART / phân loại

def feature_label(name):
    """tag_Multiplayer -> Tag: Multiplayer; genre_RPG -> Thể loại: RPG; còn lại tra bảng tên dễ đọc."""
    for prefix, key in (("tag_", "mn_feat_tag"), ("genre_", "mn_feat_genre")):
        if name.startswith(prefix):
            return f"{t(key)}: {name[len(prefix):]}"
    known = {"num_languages": "mn_feat_languages", "price_vnd": "mn_feat_price", "is_coop": "mn_feat_coop",
             "is_multiplayer": "mn_feat_multiplayer", "is_free": "mn_feat_free", "release_month": "mn_feat_month",
             "publisher_prior_games": "mn_feat_publisher"}
    return t(known[name]) if name in known else name


def importance(df, p, n=12):
    d = df.head(n).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["importance"] * 100, y=[feature_label(f) for f in d["feature"]], orientation="h",
        marker=dict(color=p.series[0]), text=[fmt.pct(v * 100) for v in d["importance"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=p.ink2, size=11),
        hovertemplate="<b>%{y}</b><br>" + t("mn_h_importance") + ": %{x:.1f}%<extra></extra>"))
    _bar_h(fig, p, height=max(240, 30 * len(d) + 60))
    fig.update_xaxes(showticklabels=False, showline=False, range=[0, d["importance"].max() * 100 * 1.25])
    return fig


def confusion(cm, labels, p):
    """Ma trận nhầm lẫn 2x2: hàng = thực tế, cột = dự đoán."""
    z = np.array(cm)
    xs, ys = [f"{t('mn_pred')}: {l}" for l in labels], [f"{t('mn_actual')}: {l}" for l in labels]
    fig = go.Figure(go.Heatmap(
        z=z, x=xs, y=ys, colorscale=[[i / (len(p.seq) - 1), c] for i, c in enumerate(p.seq)], showscale=False,
        xgap=3, ygap=3, hovertemplate="%{y}<br>%{x}<br>%{z:,}<extra></extra>"))
    style(fig, p, height=230)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=p.ink2))
    fig.update_xaxes(showline=False, side="top", tickfont=dict(color=p.ink2))
    # Số trong ô: chữ sáng trên ô đậm, chữ tối trên ô nhạt (heatmap không cho đặt màu chữ riêng từng ô)
    top = z.max()
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            fig.add_annotation(x=x, y=y, text=fmt.num(z[i][j]), showarrow=False,
                               font=dict(size=15, color="#ffffff" if z[i][j] > top * 0.55 else "#0b0b0b"))
    return fig


def model_compare(rows, p):
    """F1-macro của từng mô hình (cùng một thước đo, một màu; mô hình được chọn đặt đậm trong nhãn)."""
    d = pd.DataFrame(rows)
    fig = go.Figure(go.Bar(
        x=d["f1"], y=d["name"], orientation="h", marker=dict(color=p.series[0]),
        text=[fmt.num(v, 3) for v in d["f1"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=p.ink2, size=12),
        customdata=d["accuracy"], hovertemplate="<b>%{y}</b><br>F1-macro: %{x:.3f}<br>Accuracy: %{customdata:.3f}<extra></extra>"))
    _bar_h(fig, p, height=60 + 44 * len(d))
    fig.update_xaxes(showticklabels=False, showline=False, range=[0, 1.12])
    return fig


def review_terms(df, p):
    """Từ khóa quyết định: hệ số âm đẩy về chê (đỏ), dương đẩy về khen (xanh)."""
    d = df.sort_values("coef")
    fig = go.Figure(go.Bar(
        x=d["coef"], y=d["term"], orientation="h",
        marker=dict(color=[p.down if v < 0 else p.up for v in d["coef"]]),
        hovertemplate="<b>%{y}</b><br>" + t("mn_h_coef") + ": %{x:+.2f}<extra></extra>"))
    _bar_h(fig, p, height=max(360, 20 * len(d) + 60))
    fig.update_xaxes(title_text=t("mn_ax_coef"), zeroline=False)
    fig.add_vline(x=0, line=dict(color=p.axis, width=1))
    return fig


# ------------------------------------------------------------------ NMF

def topic_label(words, n=3):
    return " · ".join(w.strip() for w in str(words).split(",")[:n])


def topics(df, p):
    """Tỷ lệ review chê thuộc mỗi chủ đề; tên chủ đề = 3 từ đặc trưng nhất (không đặt tên tay để chạy lại vẫn đúng)."""
    d = df.sort_values("share")
    fig = go.Figure(go.Bar(
        x=d["share"] * 100, y=[topic_label(w) for w in d["top_words"]], orientation="h",
        marker=dict(color=p.series[0]), text=[fmt.pct(v * 100) for v in d["share"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=p.ink2, size=11),
        customdata=np.stack([d["top_words"], d["n_reviews"]], axis=-1),
        hovertemplate=f"<b>%{{y}}</b><br>%{{customdata[0]}}<br>{t('mn_h_reviews')}: %{{customdata[1]:,}}"
                      f" (%{{x:.1f}}%)<extra></extra>"))
    _bar_h(fig, p, height=max(300, 34 * len(d) + 60))
    fig.update_xaxes(showticklabels=False, showline=False, range=[0, d["share"].max() * 100 * 1.22])
    return fig


def coherence(metrics, p):
    return _k_line(metrics["umass_coherence"], metrics["best_k"], p, t("mn_ax_coherence"), ":.3f")
