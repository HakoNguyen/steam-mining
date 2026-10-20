"""Các biểu đồ Plotly của Smart Dashboard. Mỗi hàm nhận DataFrame (từ Metabase) + Palette, trả Figure."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from lib import fmt
from lib.i18n import t
from lib.theme import FONT, style

def weekday(d):
    """1 = Thứ 2 / Mon ... 7 = Chủ nhật / Sun."""
    return t("weekdays")[d - 1]


VND_TICKS = [20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000, 2_000_000]


def _rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _colorscale(p):
    return [[i / (len(p.seq) - 1), c] for i, c in enumerate(p.seq)]


def _ink_on(fill_rgb, p):
    """Chữ đặt trên nền màu: chọn trắng hoặc đen theo độ sáng của nền để luôn đọc được."""
    nums = [float(v) for v in fill_rgb[fill_rgb.index("(") + 1:fill_rgb.index(")")].split(",")[:3]]
    lum = (0.2126 * nums[0] + 0.7152 * nums[1] + 0.0722 * nums[2]) / 255
    return "#0b0b0b" if lum > 0.55 else "#ffffff"


def _log_ticks(lo, hi):
    """Vạch chia thang log theo dãy 1-2-5 (10, 20, 50, 100...) nằm trong [lo, hi]."""
    vals = [m * 10 ** e for e in range(0, 10) for m in (1, 2, 5)]
    return [v for v in vals if lo * 0.9 <= v <= hi * 1.1]


def _vnd_axis(fig, axis="x"):
    getattr(fig, f"update_{axis}axes")(type="log", tickvals=VND_TICKS, ticktext=[fmt.compact(v) for v in VND_TICKS])


# ------------------------------------------------------------------ Hôm nay

def top_ccu(df, p, n=10):
    d = df.nlargest(n, "peak_ccu").iloc[::-1]
    price = [t("free") if f else fmt.vnd(v) for v, f in zip(d["price_vnd"], d["is_free"])]
    fig = go.Figure(go.Bar(
        x=d["peak_ccu"], y=d["game_title"], orientation="h",
        marker=dict(color=p.series[0]),
        text=[fmt.compact(v) for v in d["peak_ccu"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=p.ink2, size=12),
        customdata=np.stack([d["genres"].fillna("—"), price], axis=-1),
        hovertemplate=f"<b>%{{y}}</b><br>{t('h_peak_ccu')}: %{{x:,.0f}}<br>{t('h_genres')}: %{{customdata[0]}}"
                      f"<br>{t('h_price')}: %{{customdata[1]}}<extra></extra>"))
    style(fig, p, height=400)
    fig.update_xaxes(showticklabels=False, showline=False, range=[0, d["peak_ccu"].max() * 1.2])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=p.ink2, size=12))
    return fig


def movers(df, p, n=6, min_snapshots=8):
    d = df.dropna(subset=["peak_ccu_change_pct"])
    d = pd.concat([d.nlargest(n, "peak_ccu_change_pct"), d.nsmallest(n, "peak_ccu_change_pct")])
    d = d.drop_duplicates("game_id").sort_values("peak_ccu_change_pct")
    low = (d["snapshots_today"] < min_snapshots) | (d["snapshots_yesterday"] < min_snapshots)
    v = d["peak_ccu_change_pct"]
    fig = go.Figure(go.Bar(
        x=v, y=d["game_title"], orientation="h",
        marker=dict(color=[p.up if x >= 0 else p.down for x in v]),
        text=[fmt.pct(x, signed=True) + (" *" if l else "") for x, l in zip(v, low)],
        textposition="outside", cliponaxis=False, textfont=dict(color=p.ink2, size=12),
        customdata=np.stack([d["peak_ccu_today"], d["peak_ccu_yesterday"],
                             d["snapshots_today"], d["snapshots_yesterday"]], axis=-1),
        hovertemplate=f"<b>%{{y}}</b><br>{t('h_change')}: %{{x:+.1f}}%<br>{t('h_ccu_today')}: %{{customdata[0]:,.0f}}"
                      f"<br>{t('h_ccu_yesterday')}: %{{customdata[1]:,.0f}}"
                      f"<br>{t('h_snapshots')}: %{{customdata[2]}} / %{{customdata[3]}}<extra></extra>"))
    style(fig, p, height=400)
    lo, hi = min(v.min(), 0), max(v.max(), 0)
    pad = (hi - lo) * 0.22 or 10
    fig.update_xaxes(showticklabels=False, showline=False, range=[lo - (pad if lo < 0 else 0), hi + pad])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=p.ink2, size=12))
    fig.add_vline(x=0, line=dict(color=p.axis, width=1))
    return fig


# ------------------------------------------------------------------ Người chơi

def _with_gaps(g, max_gap_minutes=90):
    """Chèn điểm trống khi hai lần đo cách nhau quá xa, để đường không nối qua giờ không có dữ liệu."""
    g = g.sort_values("snapshot_at_vn")
    gaps = g["snapshot_at_vn"].diff() > pd.Timedelta(minutes=max_gap_minutes)
    if not gaps.any():
        return g
    fillers = g.loc[gaps, ["snapshot_at_vn"]].copy()
    fillers["snapshot_at_vn"] -= pd.Timedelta(minutes=1)
    fillers["concurrent_players"] = np.nan
    return pd.concat([g, fillers]).sort_values("snapshot_at_vn")


def hourly(df, p, game_ids, color_of, log_scale=False):
    fig = go.Figure()
    ends = []
    for gid in game_ids:
        g = df[df["game_id"] == gid]
        if g.empty:
            continue
        name, color = g["game_title"].iloc[0], color_of[gid]
        gg = _with_gaps(g)
        # Chấm nhỏ ở mỗi lần đo: lần đo đơn lẻ (sau khoảng trống) vẫn nhìn thấy được
        fig.add_trace(go.Scatter(
            x=gg["snapshot_at_vn"], y=gg["concurrent_players"], mode="lines+markers", name=name,
            line=dict(color=color, width=2), marker=dict(color=color, size=4), connectgaps=False,
            hovertemplate=f"%{{y:,.0f}} {t('h_players')}<extra>{name}</extra>"))
        last = g.sort_values("snapshot_at_vn").iloc[-1]
        fig.add_trace(go.Scatter(
            x=[last["snapshot_at_vn"]], y=[last["concurrent_players"]], mode="markers", showlegend=False,
            marker=dict(color=color, size=9, line=dict(color=p.surface, width=2)), hoverinfo="skip"))
        ends.append((last["snapshot_at_vn"], last["concurrent_players"], name))

    style(fig, p, height=440, legend=True)
    fig.update_layout(hovermode="x unified", margin=dict(r=150))
    fig.update_xaxes(tickformat="%H:%M<br>%d/%m", showspikes=True, spikemode="across",
                     spikecolor=p.axis, spikethickness=1, spikedash="solid")
    if log_scale and ends:
        ys = df[df["game_id"].isin(game_ids)]["concurrent_players"]
        fig.update_yaxes(type="log", tickvals=_log_ticks(ys.min(), ys.max()), tickformat="~s")
    else:
        fig.update_yaxes(type="linear", tickformat="~s")

    # Nhãn cuối đường: chỉ ghi khi không đè lên nhãn khác (nếu quá sát, chú giải phía trên đã đủ)
    placed = []
    span = (np.log10(max(e[1] for e in ends)) - np.log10(max(min(e[1] for e in ends), 1))) if log_scale and ends else None
    lin_span = (max(e[1] for e in ends) - min(e[1] for e in ends)) if ends else 0
    for x, y, name in sorted(ends, key=lambda e: -e[1]):
        pos = np.log10(max(y, 1)) if log_scale else y
        gap = (span or 1) * 0.06 if log_scale else (lin_span or 1) * 0.06
        if any(abs(pos - q) < gap for q in placed):
            continue
        placed.append(pos)
        fig.add_annotation(x=x, y=pos if log_scale else y, text=name, showarrow=False, xanchor="left",
                           xshift=10, font=dict(color=p.ink2, size=12))
    return fig


def heatmap(df, p):
    z = df.pivot_table(index="dow", columns="hour_vn", values="avg_ccu").reindex(index=range(1, 8), columns=range(24))
    days = df.pivot_table(index="dow", columns="hour_vn", values="n_days").reindex(index=range(1, 8), columns=range(24))
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[f"{h}h" for h in range(24)], y=[weekday(d) for d in range(1, 8)],
        customdata=days.values, colorscale=_colorscale(p), xgap=2, ygap=2, hoverongaps=False,
        colorbar=dict(thickness=10, outlinewidth=0, len=0.9, tickformat="~s", tickfont=dict(color=p.muted, size=11),
                      title=dict(text=t("h_colorbar"), font=dict(color=p.ink2, size=12), side="right")),
        hovertemplate="%{y}, %{x}<br>%{z:,.0f} " + t("h_players_per_game") + "<br>"
                      + t("h_based_on_days", n="%{customdata}") + "<extra></extra>"))
    style(fig, p, height=340)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=p.ink2))
    fig.update_xaxes(showline=False, tickfont=dict(color=p.muted, size=11))
    return fig


# ------------------------------------------------------------------ Thị trường

def _label_points(fig, rows, p, x_log=True, x_gap=0.07, y_gap=0.045):
    """Ghi tên cho một số điểm; bỏ qua nhãn nào quá gần nhãn đã ghi để chữ không đè lên nhau."""
    if rows.empty:
        return
    xs = np.log10(rows["x"]) if x_log else rows["x"]
    x_span = (xs.max() - xs.min()) or 1
    y_span = (rows["y"].max() - rows["y"].min()) or 1
    placed = []
    for x, y, text in zip(xs, rows["y"], rows["text"]):
        if any(abs(x - px) < x_gap * 3 * x_span and abs(y - py) < y_gap * 3 * y_span for px, py in placed):
            continue
        placed.append((x, y))
        fig.add_annotation(x=x, y=y, text=text, showarrow=False, yshift=14, font=dict(color=p.ink2, size=11))


def opportunity(df, p, n_niche=6, n_big=3):
    d = df.copy()
    mx, my = d["n_games"].median(), d["pct_high_positive"].median()
    size = 7 + 32 * np.sqrt(d["avg_owners"] / d["avg_owners"].max())
    fig = go.Figure(go.Scatter(
        x=d["n_games"], y=d["pct_high_positive"], mode="markers",
        marker=dict(size=size, color=p.series[0], opacity=0.55, line=dict(color=p.surface, width=1.5)),
        customdata=np.stack([d["tag_name"], [fmt.compact(v) for v in d["avg_owners"]],
                             d["avg_positive_ratio"] * 100, [fmt.vnd(v) for v in d["median_price_vnd"]]], axis=-1),
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>%{{x}} {t('game_unit')} · %{{y:.1f}}% {t('h_rated_90')}"
                      f"<br>{t('h_avg_owners')}: %{{customdata[1]}}<br>{t('h_avg_pos')}: %{{customdata[2]:.1f}}%"
                      f"<br>{t('h_median_price')}: %{{customdata[3]}}<extra></extra>"))
    style(fig, p, height=540)
    fig.update_xaxes(type="log", showgrid=True, title_text=t("ax_competition"),
                     tickvals=_log_ticks(d["n_games"].min(), d["n_games"].max()))
    fig.update_yaxes(title_text=t("ax_rated_90"), ticksuffix="%")
    # Đường trung vị chia 4 góc (trục log: tọa độ shape/annotation tính theo log10)
    fig.add_shape(type="line", xref="x", yref="paper", x0=np.log10(mx), x1=np.log10(mx), y0=0, y1=1,
                  line=dict(color=p.axis, width=1))
    fig.add_hline(y=my, line=dict(color=p.axis, width=1))
    for key, x, y, xa, ya in (("q_niche", 0.01, 0.99, "left", "top"),
                              ("q_crowded_good", 0.99, 0.99, "right", "top"),
                              ("q_small_weak", 0.01, 0.01, "left", "bottom"),
                              ("q_saturated", 0.99, 0.01, "right", "bottom")):
        fig.add_annotation(xref="paper", yref="paper", x=x, y=y, xanchor=xa, yanchor=ya, text=t(key),
                           showarrow=False, font=dict(color=p.muted, size=11),
                           bgcolor=_rgba(p.surface, 0.85), borderpad=3)
    niche = d[(d["n_games"] < mx) & (d["pct_high_positive"] > my)].nlargest(n_niche, "pct_high_positive")
    big = d[d["n_games"] >= mx].nlargest(n_big, "avg_owners")
    picks = pd.concat([niche, big]).drop_duplicates("tag_name")
    _label_points(fig, picks.rename(columns={"n_games": "x", "pct_high_positive": "y", "tag_name": "text"}), p)
    return fig


def price_vs_rating(df, p):
    fig = go.Figure(go.Scatter(
        x=df["price_vnd"], y=df["positive_pct"], mode="markers",
        marker=dict(size=7, color=p.series[0], opacity=0.4, line=dict(width=0)),
        customdata=np.stack([df["game_title"], [fmt.vnd(v) for v in df["price_vnd"]],
                             [fmt.compact(v) for v in df["owners_mid"]]], axis=-1),
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>{t('h_price')}: %{{customdata[1]}}<br>{t('h_pos_reviews')}: %{{y:.1f}}%"
                      f"<br>{t('h_owners')}: %{{customdata[2]}}<extra></extra>"))
    style(fig, p, height=420)
    _vnd_axis(fig, "x")
    fig.update_xaxes(showgrid=True, title_text=t("ax_price_log"))
    fig.update_yaxes(title_text=t("ax_pos_reviews"), ticksuffix="%")
    fig.add_hline(y=float(df["positive_pct"].median()), line=dict(color=p.axis, width=1))
    return fig


def genre_treemap(df, p):
    d = df.sort_values("n_games", ascending=False)
    ratio = d["avg_positive_ratio"] * 100
    lo, hi = float(ratio.min()), float(ratio.max())
    scale = _colorscale(p)[1:-1]  # bỏ 2 đầu quá nhạt/quá đậm để ô nào cũng có màu rõ
    scale = [[i / (len(scale) - 1), c] for i, (_, c) in enumerate(scale)]
    fills = sample_colorscale(scale, ((ratio - lo) / ((hi - lo) or 1)).clip(0, 1).tolist())
    fig = go.Figure(go.Treemap(
        labels=d["genre_name"], parents=[""] * len(d), values=d["n_games"],
        marker=dict(colors=fills, line=dict(color=p.surface, width=2)),
        textfont=dict(family=FONT, size=13, color=[_ink_on(c, p) for c in fills]),
        texttemplate="<b>%{label}</b><br>%{value} " + t("game_unit"),
        customdata=np.stack([ratio, [fmt.compact(v) for v in d["avg_owners"]],
                             [fmt.vnd(v) for v in d["median_price_vnd"]], d["pct_free"]], axis=-1),
        hovertemplate=f"<b>%{{label}}</b><br>%{{value}} {t('game_unit')}<br>{t('h_avg_pos')}: %{{customdata[0]:.1f}}%"
                      f"<br>{t('h_avg_owners')}: %{{customdata[1]}}<br>{t('h_median_price')}: %{{customdata[2]}}"
                      f"<br>{t('h_free_share')}: %{{customdata[3]:.1f}}%<extra></extra>",
        tiling=dict(pad=2), root=dict(color="rgba(0,0,0,0)")))
    style(fig, p, height=420)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    return fig


def price_box(df, p):
    order = df.groupby("genre_name")["price_vnd"].median().sort_values().index
    fig = go.Figure()
    for g in order:
        fig.add_trace(go.Box(
            x=df.loc[df["genre_name"] == g, "price_vnd"], name=g, orientation="h", boxpoints="outliers",
            marker=dict(color=p.series[0], size=4, opacity=0.5), line=dict(color=p.series[0], width=1.5),
            fillcolor=_rgba(p.series[0], 0.12), hoveron="boxes"))
    style(fig, p, height=420)
    _vnd_axis(fig, "x")
    fig.update_xaxes(showgrid=True, title_text=t("ax_price_log"))
    fig.update_yaxes(showgrid=False, tickfont=dict(color=p.ink2, size=12))
    return fig


def discounts(df, p):
    d = df.sort_values("discount_pct")
    seg_x, seg_y = [], []
    for _, r in d.iterrows():
        seg_x += [r["price_initial_vnd"], r["price_vnd"], None]
        seg_y += [r["game_title"], r["game_title"], None]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=seg_x, y=seg_y, mode="lines", line=dict(color=p.grid, width=3),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=d["price_initial_vnd"], y=d["game_title"], mode="markers", name=t("h_initial"),
        marker=dict(color=p.muted, size=9, line=dict(color=p.surface, width=2)),
        hovertemplate=t("h_initial") + ": %{x:,.0f} ₫<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=d["price_vnd"], y=d["game_title"], mode="markers+text", name=t("h_sale"),
        marker=dict(color=p.series[0], size=11, line=dict(color=p.surface, width=2)),
        text=[f"−{int(v)}%" for v in d["discount_pct"]], textposition="middle left",
        textfont=dict(color=p.ink2, size=11),
        hovertemplate=t("h_sale") + ": %{x:,.0f} ₫<extra></extra>"))
    style(fig, p, height=max(320, 34 * len(d) + 60), legend=True)
    _vnd_axis(fig, "x")
    # Nới trục bên trái để nhãn "−90%" (đặt bên trái điểm giá thấp nhất) không dính mép
    lo, hi = d["price_vnd"].min(), d["price_initial_vnd"].max()
    fig.update_xaxes(showgrid=True, title_text=t("ax_price_log"),
                     range=[np.log10(lo * 0.45), np.log10(hi * 1.15)])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=p.ink2, size=12))
    fig.update_layout(hovermode="y unified")
    return fig
