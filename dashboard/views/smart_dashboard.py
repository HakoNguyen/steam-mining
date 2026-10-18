import pandas as pd
import streamlit as st

from lib import charts, fmt, insights, metabase
from lib.i18n import t, tab_labels
from lib.theme import palette, show

p = palette()


def _ts(s):
    """Thời gian từ Metabase (chuỗi ISO, có thể kèm 'Z') -> datetime không múi giờ."""
    ts = pd.to_datetime(s)
    return ts.dt.tz_localize(None) if getattr(ts.dt, "tz", None) is not None else ts


def cols(df, **keys):
    """Chọn và đổi tên cột cho bảng số liệu theo ngôn ngữ: cols(df, game_title="col_game", ...)."""
    return df[list(keys)].rename(columns={c: t(k) for c, k in keys.items()})


def takeaways(lines):
    if lines:
        with st.container(border=True):
            st.markdown(f"**{t('insights')}**")
            st.markdown("\n".join(f"- {s}" for s in lines))


def card(title, caption, fig, table=None):
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.caption(caption)
        show(fig)
        if table is not None:
            with st.expander(t("table_view")):
                st.dataframe(table, hide_index=True, width="stretch")


def line_colors(selected):
    """Màu gắn theo game, không theo thứ tự: bỏ chọn một game thì các game còn lại giữ nguyên màu."""
    slots = st.session_state.setdefault("line_slots", {})
    for gid in [g for g in slots if g not in selected]:
        del slots[gid]
    used = set(slots.values())
    for gid in selected:
        if gid not in slots:
            slots[gid] = next(i for i in range(4) if i not in used)
            used.add(slots[gid])
    return {gid: p.series[slots[gid]] for gid in selected}


try:
    kpi_ccu = metabase.run("[Streamlit] KPI CCU theo ngày")
    kpi = metabase.run("[Streamlit] KPI thị trường").iloc[0]
    top50 = metabase.run("[Streamlit] Top 50 hôm nay")
    movers = metabase.run("[Streamlit] Biến động top 50")
    hourly = metabase.run("[Streamlit] CCU theo giờ (top 50, 7 ngày)")
    heat = metabase.run("[Streamlit] CCU theo giờ và thứ")
    tags = metabase.run("[Streamlit] Thị trường theo tag")
    genres = metabase.run("[Streamlit] Thị trường theo thể loại")
    price_rating = metabase.run("[Streamlit] Giá và tỷ lệ khen")
    price_genre = metabase.run("[Streamlit] Giá theo thể loại")
    deals = metabase.run("[Streamlit] Game giảm giá sâu")
except Exception as e:  # Metabase chưa chạy hoặc thiếu API key
    st.error(t("sd_error", e=e))
    st.stop()

hourly["snapshot_at_vn"] = _ts(hourly["snapshot_at_vn"])
report_date = _ts(top50["full_date"]).iloc[0]

# ------------------------------------------------------------------ Đầu trang + KPI
st.title(t("nav_smart"))
st.caption(t("sd_subtitle", date=f"{report_date:%d/%m/%Y}"))

series = kpi_ccu.sort_values("full_date")["total_peak_ccu"].tolist()
latest, prev = series[-1], (series[-2] if len(series) > 1 else None)
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric(t("kpi_ccu"), fmt.compact(latest),
          delta=fmt.pct((latest - prev) / prev * 100, signed=True) if prev else None,
          delta_description=t("kpi_ccu_delta"), chart_data=series, chart_type="area", border=True,
          help=t("kpi_ccu_help"))
k2.metric(t("kpi_games"), fmt.num(kpi["n_games"]), border=True, help=t("kpi_games_help"))
k3.metric(t("kpi_price"), fmt.vnd(kpi["median_price_vnd"]), border=True, help=t("kpi_price_help"))
k4.metric(t("kpi_free"), fmt.pct(kpi["pct_free"] * 100), border=True, help=t("kpi_free_help"))
k5.metric(t("kpi_discount"), fmt.num(kpi["n_deep_discount"]), border=True, help=t("kpi_discount_help"))

# key + on_change: nhớ tab đang mở khi đổi ngôn ngữ / sáng tối (nội dung vẫn vẽ đủ cả 3 tab nên chuyển tab tức thì)
tab_today, tab_players, tab_market = st.tabs(tab_labels("sd_tab", ["tab_today", "tab_players", "tab_market"]),
                                             key="sd_tab", on_change="rerun")

# ------------------------------------------------------------------ Hôm nay
with tab_today:
    takeaways(insights.today(top50, movers, kpi))
    left, right = st.columns(2)
    with left:
        card(t("c_top10_title"), t("c_top10_cap"), charts.top_ccu(top50, p),
             cols(top50.nlargest(10, "peak_ccu"), game_title="col_game", peak_ccu="col_peak_ccu",
                  genres="col_genres", price_vnd="col_price"))
    with right:
        card(t("c_movers_title"), t("c_movers_cap"), charts.movers(movers, p),
             cols(movers.sort_values("peak_ccu_change_pct", ascending=False),
                  game_title="col_game", peak_ccu_change_pct="col_change", peak_ccu_today="col_ccu_today",
                  peak_ccu_yesterday="col_ccu_yesterday", snapshots_today="col_snaps_today",
                  snapshots_yesterday="col_snaps_yesterday"))

# ------------------------------------------------------------------ Người chơi
with tab_players:
    takeaways(insights.players(heat))
    ranked = top50.sort_values("peak_ccu", ascending=False)
    titles = dict(zip(ranked["game_id"], ranked["game_title"]))
    f1, f2 = st.columns([4, 1], vertical_alignment="bottom")
    selected = f1.multiselect(t("c_hourly_select"), options=list(titles),
                              default=list(titles)[:3], format_func=titles.get, max_selections=4, key="hourly_games")
    log_scale = f2.toggle(t("c_hourly_log"), value=True, help=t("c_hourly_log_help"), key="hourly_log")
    if selected:
        card(t("c_hourly_title"), t("c_hourly_cap"),
             charts.hourly(hourly, p, selected, line_colors(selected), log_scale),
             cols(hourly[hourly["game_id"].isin(selected)], snapshot_at_vn="col_time", game_title="col_game",
                  concurrent_players="col_players"))
    else:
        st.info(t("c_hourly_empty"))
    card(t("c_heat_title"), t("c_heat_cap"), charts.heatmap(heat, p),
         cols(heat.sort_values(["dow", "hour_vn"]).assign(dow=lambda d: d["dow"].map(charts.weekday)),
              dow="col_weekday", hour_vn="col_hour", avg_ccu="col_avg_ccu", n_days="col_days"))

# ------------------------------------------------------------------ Thị trường
with tab_market:
    takeaways(insights.market(tags, genres, price_genre, kpi))
    card(t("c_opp_title"), t("c_opp_cap"), charts.opportunity(tags, p),
         cols(tags.sort_values("pct_high_positive", ascending=False),
              tag_name="col_tag", n_games="col_n_games", pct_high_positive="col_high_pos",
              avg_owners="col_avg_owners", avg_positive_ratio="col_avg_pos", median_price_vnd="col_median_price"))
    left, right = st.columns(2)
    with left:
        card(t("c_pr_title"), t("c_pr_cap"), charts.price_vs_rating(price_rating, p),
             cols(price_rating, game_title="col_game", price_vnd="col_price", positive_pct="col_pos_pct",
                  owners_mid="col_owners"))
    with right:
        card(t("c_tree_title"), t("c_tree_cap"), charts.genre_treemap(genres, p),
             cols(genres.sort_values("n_games", ascending=False),
                  genre_name="col_genre", n_games="col_n_games", avg_owners="col_avg_owners",
                  avg_positive_ratio="col_avg_pos", pct_high_positive="col_high_pos",
                  median_price_vnd="col_median_price", pct_free="col_free_pct"))
    left, right = st.columns(2)
    with left:
        card(t("c_box_title"), t("c_box_cap"), charts.price_box(price_genre, p),
             cols(price_genre.groupby("genre_name")["price_vnd"].describe().reset_index(),
                  genre_name="col_genre", count="col_n_games", **{"25%": "col_p25", "50%": "col_median_price",
                                                                  "75%": "col_p75"}))
    with right:
        card(t("c_deal_title"), t("c_deal_cap"), charts.discounts(deals, p),
             cols(deals, game_title="col_game", price_initial_vnd="col_initial_price", price_vnd="col_sale_price",
                  discount_pct="col_discount", owners_mid="col_owners"))
