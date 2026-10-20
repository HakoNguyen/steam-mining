"""'Điểm chính' đầu mỗi tab: vài câu kết luận tính thẳng từ dữ liệu (không dùng AI), để người xem
nắm ý chính trước khi đọc biểu đồ. Mỗi hàm trả danh sách câu markdown; thiếu dữ liệu thì bỏ câu đó."""
from lib import fmt
from lib.charts import weekday
from lib.i18n import lang, t


def _x(v):
    return fmt.num(v, 1) if lang() == "vi" else f"{v:.1f}"


def today(top50, movers, kpi, min_snapshots=8):
    out = []
    r = top50.nlargest(2, "peak_ccu")
    if len(r) == 2:
        a, b = r.iloc[0], r.iloc[1]
        out.append(t("ins_leader", g1=a["game_title"], ccu=fmt.compact(a["peak_ccu"]),
                     x=_x(a["peak_ccu"] / b["peak_ccu"]), g2=b["game_title"]))
    # chỉ dùng game đo đủ cả 2 ngày để không kết luận từ dữ liệu thiếu
    m = movers.dropna(subset=["peak_ccu_change_pct"])
    m = m[(m["snapshots_today"] >= min_snapshots) & (m["snapshots_yesterday"] >= min_snapshots)]
    if len(m) >= 2:
        up, down = m.nlargest(1, "peak_ccu_change_pct").iloc[0], m.nsmallest(1, "peak_ccu_change_pct").iloc[0]
        out.append(t("ins_movers", up=up["game_title"], up_pct=fmt.pct(up["peak_ccu_change_pct"], signed=True),
                     down=down["game_title"], down_pct=fmt.pct(down["peak_ccu_change_pct"], signed=True)))
    out.append(t("ins_deals", n=fmt.num(kpi["n_deep_discount"])))
    return out


def sellers(top_sellers, k=15):
    if top_sellers.empty:
        return []
    first = top_sellers.sort_values("rank").iloc[0]
    if bool(first["is_upcoming"]) and isinstance(first["release_date"], str):
        out = [t("ins_seller_upcoming", g=first["game_title"], date=fmt.short_date(first["release_date"]))]
    else:
        out = [t("ins_seller", g=first["game_title"])]
    top = top_sellers.nsmallest(k, "rank")
    out.append(t("ins_seller_overlap", n=int(top["most_played_rank"].notna().sum()), k=len(top)))
    return out


def players(heat):
    if heat.empty:
        return []
    top = heat.loc[heat["avg_ccu"].idxmax()]
    out = [t("ins_peak", hour=int(top["hour_vn"]), day=weekday(int(top["dow"])), ccu=fmt.compact(top["avg_ccu"]))]
    days = int(heat["n_days"].max())
    if days < 4:  # mỗi ô (thứ, giờ) cần vài tuần mới có nhiều ngày đo
        out.append(t("ins_days", n=days))
    return out


def market(tags, genres, price_genre, kpi):
    out = []
    mx, my = tags["n_games"].median(), tags["pct_high_positive"].median()
    niche = tags[(tags["n_games"] < mx) & (tags["pct_high_positive"] > my)]
    if not niche.empty:
        n = niche.loc[niche["pct_high_positive"].idxmax()]
        out.append(t("ins_niche", tag=n["tag_name"], n=int(n["n_games"]), p=fmt.pct(n["pct_high_positive"], 0)))
    if not genres.empty:
        g = genres.loc[genres["avg_owners"].idxmax()]
        out.append(t("ins_genre", genre=g["genre_name"], owners=fmt.compact(g["avg_owners"])))
    if not price_genre.empty:
        med = price_genre.groupby("genre_name")["price_vnd"].median()
        out.append(t("ins_price", price=fmt.vnd(kpi["median_price_vnd"]), genre=med.idxmax(), gprice=fmt.vnd(med.max())))
    return out
