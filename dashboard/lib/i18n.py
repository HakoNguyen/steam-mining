"""Chữ hiển thị bằng 2 ngôn ngữ. Ngôn ngữ lưu trong session_state["lang"] (bộ chọn ở thanh bên)
và trên URL (?lang=en) để chuyển trang hay gửi link vẫn giữ đúng ngôn ngữ."""
import streamlit as st

LANGS = {"vi": "Tiếng Việt", "en": "English"}
DEFAULT = "vi"

STR = {
    # ---- chung / điều hướng
    "nav_home": ("Trang chủ", "Home"),
    "nav_analysis": ("Phân tích", "Analytics"),
    "nav_smart": ("Smart Dashboard", "Smart Dashboard"),
    "nav_explore": ("Khám phá dữ liệu", "Data Explorer"),
    "nav_ai": ("Trợ lý AI", "AI Assistant"),
    "nav_copilot": ("Copilot", "Copilot"),
    "lang_label": ("Ngôn ngữ", "Language"),
    "table_view": ("Bảng số liệu", "Data table"),
    "insights": ("Điểm chính", "Key takeaways"),
    "free": ("Miễn phí", "Free"),
    "game_unit": ("game", "games"),

    # ---- trang chủ
    "home_intro": ("Kho dữ liệu và khai phá dữ liệu thị trường game Steam: theo dõi **top 50 game mỗi giờ** "
                   "và phân tích **~2.000 game nhiều người sở hữu nhất** mỗi tuần.",
                   "A data warehouse and data-mining platform for the Steam game market: the **top 50 games tracked "
                   "every hour** and the **~2,000 most-owned games** analysed every week."),
    "home_start": ("Bắt đầu từ đâu", "Where to start"),
    "home_smart_desc": ("Kết luận nhanh về thị trường hôm nay: game đông người chơi, biến động, giờ cao điểm, "
                        "cơ hội theo tag, giá và giảm giá.",
                        "Quick answers about today's market: most-played games, movers, peak hours, tag "
                        "opportunities, prices and discounts."),
    "home_explore_desc": ("Dashboard Metabase nhúng trực tiếp để tự đào sâu: biểu đồ thêm hoặc sửa trên Metabase hiện ngay tại đây.",
                          "The Metabase dashboard embedded for self-service analysis: charts added or edited in "
                          "Metabase show up here instantly."),
    "home_copilot_desc": ("Trợ lý khảo sát thị trường cho nhà phát hành nhỏ và người chơi (đang phát triển).",
                          "A market-research assistant for indie publishers and players (in development)."),
    "home_open": ("Mở {title}", "Open {title}"),

    # ---- KPI
    "kpi_ccu": ("Tổng CCU đỉnh · top 50", "Total peak CCU · top 50"),
    "kpi_ccu_delta": ("so với hôm trước", "vs previous day"),
    "kpi_ccu_help": ("Tổng số người chơi đồng thời cao nhất trong ngày của 50 game hot nhất.",
                     "Sum of the daily peak concurrent players of the 50 hottest games."),
    "kpi_games": ("Game trong tập phân tích", "Games analysed"),
    "kpi_games_help": ("~2.000 game nhiều người sở hữu nhất (loại game), cập nhật hằng tuần.",
                       "The ~2,000 most-owned games (type = game), refreshed weekly."),
    "kpi_price": ("Giá trung vị", "Median price"),
    "kpi_price_help": ("Giá phổ biến của game trả phí trên Steam Việt Nam.", "Typical price of paid games on Steam Vietnam."),
    "kpi_free": ("Tỷ lệ miễn phí", "Free-to-play share"),
    "kpi_free_help": ("Phần trăm game free-to-play trong tập phân tích.", "Share of free-to-play games in the analysed set."),
    "kpi_discount": ("Top 50 giảm giá ≥ 50%", "Top 50 on ≥ 50% sale"),
    "kpi_discount_help": ("Số game trong top 50 đang giảm giá từ 50% trở lên.", "Top-50 games currently discounted by 50% or more."),

    # ---- Smart Dashboard
    "sd_error": ("Không lấy được dữ liệu từ Metabase ({e}). Kiểm tra Metabase đang chạy và METABASE_API_KEY trong .env.",
                 "Could not load data from Metabase ({e}). Check that Metabase is running and METABASE_API_KEY is set in .env."),
    "sd_subtitle": ("Thị trường game Steam · số liệu ngày **{date}**", "Steam game market · data for **{date}**"),
    "tab_today": ("Hôm nay", "Today"),
    "tab_players": ("Người chơi", "Players"),
    "tab_market": ("Thị trường", "Market"),
    "c_top10_title": ("Top 10 game đông người chơi nhất", "Top 10 most-played games"),
    "c_top10_cap": ("CCU đỉnh trong ngày. Rê chuột để xem thể loại và giá.", "Daily peak CCU. Hover for genres and price."),
    "c_movers_title": ("Tăng / giảm mạnh nhất so với hôm trước", "Biggest risers and fallers vs previous day"),
    "c_movers_cap": ("Thay đổi CCU đỉnh. Xanh: tăng · đỏ: giảm · dấu * : một trong hai ngày đo dưới 8 lần nên kém tin cậy.",
                     "Change in peak CCU. Blue: up · red: down · * : fewer than 8 measurements on one of the two days, less reliable."),
    "c_sellers_title": ("Bán chạy nhất trên Steam Việt Nam", "Top sellers on Steam Vietnam"),
    "c_sellers_cap": ("Bảng xếp hạng bán chạy chính thức của Steam ngày {date}, gồm cả game đang cho đặt trước. "
                      "Cột \"Hạng người chơi\": thứ hạng của game đó trong top 50 nhiều người chơi.",
                      "Steam's official top-sellers chart for {date}, including pre-orders. "
                      "\"Most-played rank\": the game's position in the top 50 most played."),
    "c_hourly_select": ("Game hiển thị trên biểu đồ CCU theo giờ (tối đa 4)", "Games on the hourly CCU chart (up to 4)"),
    "c_hourly_log": ("Thang log", "Log scale"),
    "c_hourly_log_help": ("Bật khi game lớn (vd. CS2) làm game nhỏ dẹt sát đáy.",
                          "Turn on when a huge game (e.g. CS2) flattens the smaller ones."),
    "c_hourly_title": ("Người chơi online theo giờ (giờ Việt Nam)", "Players online by hour (Vietnam time)"),
    "c_hourly_cap": ("Mỗi chấm là một lần đo mỗi giờ trong 7 ngày gần nhất. Khoảng trống: giờ hệ thống thu thập không chạy.",
                     "Each dot is an hourly measurement over the last 7 days. Gaps: hours when the collector was not running."),
    "c_hourly_empty": ("Chọn ít nhất một game để xem biểu đồ.", "Select at least one game to see the chart."),
    "c_heat_title": ("Giờ nào đông người chơi nhất?", "When do people play the most?"),
    "c_heat_cap": ("CCU trung bình mỗi game trong top 50, theo giờ trong ngày và thứ trong tuần (giờ Việt Nam). "
                   "Ô trống: chưa có lần đo nào vào khung giờ đó.",
                   "Average CCU per top-50 game by hour of day and day of week (Vietnam time). "
                   "Empty cells: no measurement yet for that slot."),
    "c_opp_title": ("Bản đồ cơ hội theo tag", "Tag opportunity map"),
    "c_opp_cap": ("Mỗi bong bóng là một tag có ≥ 20 game; bong bóng càng to, game có tag đó càng nhiều người sở hữu. "
                  "Đường kẻ là trung vị. Góc trên-trái: ít đối thủ mà nhiều game được khen ≥ 90%.",
                  "Each bubble is a tag with ≥ 20 games; bigger bubbles mean more owners per game. Lines mark the medians. "
                  "Top-left: few competitors and many games rated ≥ 90% positive."),
    "c_pr_title": ("Giá cao có được khen nhiều hơn?", "Do pricier games get better reviews?"),
    "c_pr_cap": ("Mỗi điểm là một game trả phí có ≥ 50 review. Đường ngang: tỷ lệ khen trung vị.",
                 "Each dot is a paid game with ≥ 50 reviews. Horizontal line: median positive share."),
    "c_tree_title": ("Các thể loại lớn cỡ nào?", "How big is each genre?"),
    "c_tree_cap": ("Diện tích: số game; màu đậm hơn: tỷ lệ khen trung bình cao hơn (thể loại có ≥ 10 game).",
                   "Area: number of games; darker: higher average positive share (genres with ≥ 10 games)."),
    "c_box_title": ("Mỗi thể loại thường bán giá bao nhiêu?", "What does each genre usually cost?"),
    "c_box_cap": ("Hộp: 50% game ở giữa; vạch trong hộp: giá trung vị; chấm: game giá bất thường. Game trả phí, 8 thể loại nhiều game nhất.",
                  "Box: middle 50% of games; line: median price; dots: unusual prices. Paid games, 8 largest genres."),
    "c_deal_title": ("Đang giảm giá sâu", "Deep discounts right now"),
    "c_deal_cap": ("Game nhiều người sở hữu nhất đang giảm từ 50% trở lên: giá gốc (xám) → giá sau giảm (xanh).",
                   "Most-owned games discounted by 50% or more: original price (grey) → sale price (blue)."),

    # ---- điểm chính (insights)
    "ins_leader": ("**{g1}** dẫn đầu với **{ccu}** người chơi cùng lúc, gấp **{x}** lần {g2}.",
                   "**{g1}** leads with **{ccu}** concurrent players, **{x}×** {g2}."),
    "ins_movers": ("**{up}** tăng mạnh nhất (**{up_pct}**); **{down}** giảm mạnh nhất (**{down_pct}**).",
                   "**{up}** rose the most (**{up_pct}**); **{down}** fell the most (**{down_pct}**)."),
    "ins_deals": ("**{n}** game trong top 50 đang giảm giá từ 50% trở lên.", "**{n}** top-50 games are on a 50%+ sale."),
    "ins_seller": ("**{g}** đang bán chạy nhất tại Việt Nam.", "**{g}** is the top seller in Vietnam."),
    "ins_seller_upcoming": ("**{g}** đang bán chạy nhất tại Việt Nam dù chưa phát hành (ra mắt {date}).",
                            "**{g}** is the top seller in Vietnam before it has even launched (out {date})."),
    "ins_seller_overlap": ("**{n}/{k}** game bán chạy nhất cũng nằm trong top 50 nhiều người chơi.",
                           "**{n} of the top {k}** sellers are also in the top 50 most played."),
    "ins_peak": ("Khung giờ đông nhất: **{hour}h {day}** (giờ VN), trung bình **{ccu}** người chơi mỗi game.",
                 "Busiest slot: **{hour}:00 on {day}** (Vietnam time), **{ccu}** players per game on average."),
    "ins_days": ("Mỗi ô giờ mới có số liệu của tối đa **{n} ngày** nên quy luật theo thứ còn sơ bộ; hệ thống chạy thêm vài tuần sẽ rõ hơn.",
                 "Each slot is based on at most **{n} day(s)** of data, so weekly patterns are still preliminary; a few more weeks will sharpen them."),
    "ins_niche": ("Ngách nổi bật: **{tag}**, chỉ {n} game nhưng **{p}** được khen ≥ 90%.",
                  "Standout niche: **{tag}**, only {n} games yet **{p}** are rated ≥ 90% positive."),
    "ins_genre": ("**{genre}** có lượng người sở hữu trung bình cao nhất (**{owners}**/game).",
                  "**{genre}** has the highest average ownership (**{owners}** per game)."),
    "ins_price": ("Giá trung vị game trả phí là **{price}**; thể loại có giá trung vị cao nhất: **{genre}** ({gprice}).",
                  "Median paid-game price is **{price}**; the priciest genre by median: **{genre}** ({gprice})."),

    # ---- cột bảng số liệu
    "col_game": ("Game", "Game"), "col_peak_ccu": ("CCU đỉnh", "Peak CCU"), "col_genres": ("Thể loại", "Genres"),
    "col_price": ("Giá (₫)", "Price (₫)"), "col_change": ("Thay đổi (%)", "Change (%)"),
    "col_ccu_today": ("CCU đỉnh hôm nay", "Peak CCU today"), "col_ccu_yesterday": ("CCU đỉnh hôm trước", "Peak CCU previous day"),
    "col_snaps_today": ("Lần đo hôm nay", "Measurements today"), "col_snaps_yesterday": ("Lần đo hôm trước", "Measurements previous day"),
    "col_time": ("Thời điểm (VN)", "Time (Vietnam)"), "col_players": ("Người chơi", "Players"),
    "col_weekday": ("Thứ", "Day"), "col_hour": ("Giờ", "Hour"), "col_avg_ccu": ("CCU TB / game", "Avg CCU / game"),
    "col_days": ("Số ngày đo", "Days measured"), "col_tag": ("Tag", "Tag"), "col_n_games": ("Số game", "Games"),
    "col_high_pos": ("% khen ≥ 90%", "% rated ≥ 90%"), "col_avg_owners": ("Owners TB", "Avg owners"),
    "col_avg_pos": ("Tỷ lệ khen TB", "Avg positive share"), "col_median_price": ("Giá trung vị (₫)", "Median price (₫)"),
    "col_genre": ("Thể loại", "Genre"), "col_pos_pct": ("% review khen", "% positive reviews"), "col_owners": ("Owners", "Owners"),
    "col_free_pct": ("% miễn phí", "% free"), "col_p25": ("Giá P25 (₫)", "P25 price (₫)"), "col_p75": ("Giá P75 (₫)", "P75 price (₫)"),
    "col_initial_price": ("Giá gốc (₫)", "Original price (₫)"), "col_sale_price": ("Giá sau giảm (₫)", "Sale price (₫)"),
    "col_discount": ("% giảm", "% off"),
    "col_rank": ("Hạng", "Rank"), "col_rank_change": ("So với hôm trước", "vs previous day"),
    "col_note": ("Ghi chú", "Note"), "col_price_text": ("Giá", "Price"), "col_mp_rank": ("Hạng người chơi", "Most-played rank"),
    "rank_new": ("Mới", "New"), "upcoming": ("Sắp ra mắt {date}", "Coming {date}"),

    # ---- biểu đồ (tooltip, trục, chú thích)
    "h_peak_ccu": ("CCU đỉnh", "Peak CCU"), "h_genres": ("Thể loại", "Genres"), "h_price": ("Giá", "Price"),
    "h_change": ("Thay đổi", "Change"), "h_ccu_today": ("CCU đỉnh hôm nay", "Peak CCU today"),
    "h_ccu_yesterday": ("CCU đỉnh hôm trước", "Peak CCU previous day"), "h_snapshots": ("Số lần đo", "Measurements"),
    "h_players": ("người chơi", "players"), "h_players_per_game": ("người chơi / game", "players per game"),
    "h_based_on_days": ("Dựa trên {n} ngày đo", "Based on {n} days of data"),
    "h_colorbar": ("CCU TB / game", "Avg CCU / game"),
    "h_rated_90": ("game được khen ≥ 90%", "games rated ≥ 90%"), "h_avg_owners": ("Owners trung bình", "Avg owners"),
    "h_avg_pos": ("Tỷ lệ khen TB", "Avg positive share"), "h_median_price": ("Giá trung vị", "Median price"),
    "h_pos_reviews": ("Review khen", "Positive reviews"), "h_owners": ("Owners", "Owners"), "h_free_share": ("Miễn phí", "Free"),
    "h_initial": ("Giá gốc", "Original price"), "h_sale": ("Giá sau giảm", "Sale price"),
    "ax_competition": ("Số game có tag này: mức cạnh tranh (thang log)", "Games with this tag: competition (log scale)"),
    "ax_rated_90": ("% game được khen ≥ 90%", "% of games rated ≥ 90%"),
    "ax_price_log": ("Giá bán (₫, thang log)", "Price (₫, log scale)"),
    "ax_pos_reviews": ("% review khen", "% positive reviews"),
    "q_niche": ("Ngách tiềm năng: ít đối thủ, được khen nhiều", "Niche: few competitors, well reviewed"),
    "q_crowded_good": ("Đông đúc nhưng được khen", "Crowded but well reviewed"),
    "q_small_weak": ("Ít game, ít được khen", "Few games, weaker reviews"),
    "q_saturated": ("Bão hòa: đông và khó được khen", "Saturated: crowded and hard to please"),
    "weekdays": (("Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"),
                 ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")),

    # ---- Khám phá dữ liệu / Copilot
    "ex_caption": ("Dashboard Metabase nhúng trực tiếp để tự lọc và đào sâu.",
                   "The Metabase dashboard, embedded for self-service filtering and drill-down."),
    "ex_missing": ("Thiếu METABASE_EMBED_SECRET trong .env. Chạy scripts/metabase_dashboard.py để bật nhúng.",
                   "METABASE_EMBED_SECRET is missing from .env. Run scripts/metabase_dashboard.py to enable embedding."),
    "ex_error": ("Không tạo được liên kết nhúng Metabase ({e}).", "Could not create the Metabase embed link ({e})."),
    "ex_open": ("Mở trong Metabase", "Open in Metabase"),
    "cp_caption": ("Trợ lý khảo sát thị trường cho nhà phát hành game nhỏ và người chơi.",
                   "A market-research assistant for indie game publishers and players."),
    "cp_info": ("Đang phát triển. Copilot sẽ trả lời các câu hỏi như *\"muốn làm game co-op indie thì nên chọn tag nào, "
                "bán giá bao nhiêu, đối thủ là ai?\"* bằng số liệu thật trong warehouse và kết quả Data Mining.",
                "In development. Copilot will answer questions like *\"for an indie co-op game, which tags should I pick, "
                "what price, and who are the competitors?\"* using real warehouse data and data-mining results."),
}


def lang():
    try:
        value = st.session_state.get("lang")
    except Exception:  # ngoài Streamlit runtime (vd. script xuất ảnh)
        return DEFAULT
    return value if value in LANGS else DEFAULT


def t(key, **kw):
    text = STR[key][0 if lang() == "vi" else 1]
    return text.format(**kw) if kw and isinstance(text, str) else text


def tab_labels(state_key, keys):
    """Nhãn tab theo ngôn ngữ hiện tại. Tab đang mở (lưu theo nhãn trong session_state[state_key])
    được dịch sang nhãn tương ứng khi đổi ngôn ngữ, để không bị nhảy về tab đầu."""
    labels = [t(k) for k in keys]
    current = st.session_state.get(state_key)
    if current is not None and current not in labels:
        for i in (0, 1):
            other = [STR[k][i] for k in keys]
            if current in other:
                st.session_state[state_key] = labels[other.index(current)]
                break
    return labels


def selector():
    """Bộ chọn ngôn ngữ ở thanh bên; giữ ngôn ngữ trên URL (?lang=en)."""
    if "lang" not in st.session_state:
        q = st.query_params.get("lang", DEFAULT)
        st.session_state["lang"] = q if q in LANGS else DEFAULT
    st.sidebar.radio(STR["lang_label"][0 if lang() == "vi" else 1], options=list(LANGS),
                     format_func=LANGS.get, key="lang", horizontal=True)
    st.query_params["lang"] = st.session_state["lang"]
