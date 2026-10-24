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
    "home_copilot_desc": ("Trợ lý khảo sát thị trường cho nhà phát hành nhỏ và người chơi: hỏi đáp bằng số liệu thật trong kho dữ liệu.",
                          "A market-research assistant for indie publishers and players, answering with real warehouse data."),
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
    "cp_examples": ("Câu hỏi mẫu", "Example questions"),
    "cp_new": ("Hỏi mới", "New chat"),
    "cp_download": ("Tải hội thoại", "Download chat"),
    "cp_model": ("{provider} · {model} · chỉ đọc dữ liệu", "{provider} · {model} · read-only"),
    "cp_model_label": ("Mô hình AI", "AI model"),
    "cp_model_help": ("Chọn mô hình trả lời. Mỗi câu trả lời ghi lại mô hình đã dùng, đổi giữa chừng vẫn giữ hội thoại.",
                      "Choose the model that answers. Each answer records the model used; switching keeps the conversation."),
    "cp_key_expired": ("khóa hết hạn", "key expired"),
    "cp_provider_unavailable": ("thiếu thư viện", "library missing"),
    "cp_key_invalid": ("Khóa API của {provider} không hợp lệ hoặc đã hết hạn ({var} trong .env). Chọn mô hình khác hoặc thay khóa.",
                       "The {provider} API key is invalid or expired ({var} in .env). Pick another model or replace the key."),
    "cp_open_evidence": ("Luôn mở phần tra cứu", "Always show lookups"),
    "cp_welcome": ("Xin chào! Tôi tra cứu kho dữ liệu ~2.000 game Steam nhiều người sở hữu nhất để trả lời câu hỏi về "
                   "thị trường: nên làm game gì, chọn tag nào, bán giá bao nhiêu, đối thủ là ai. Mọi con số đều kèm "
                   "truy vấn đã chạy để bạn kiểm tra.",
                   "Hi! I look up a warehouse of the ~2,000 most-owned Steam games to answer market questions: what to "
                   "build, which tags, what price, who the competitors are. Every number comes with the query I ran so "
                   "you can check it."),
    "cp_try": ("Thử hỏi:", "Try asking:"),
    "cp_limits": ("Dữ liệu chỉ gồm các game đã thành công (thiên lệch người sống sót); owners là ước lượng của SteamSpy.",
                  "Data covers successful games only (survivorship bias); owners are SteamSpy estimates."),
    "cp_placeholder": ("Hỏi về thể loại, tag, giá bán, đối thủ...", "Ask about genres, tags, prices, competitors..."),
    "cp_ex_market": ("Thị trường game Souls-like có đáng làm không, đối thủ nhiều không?",
                     "Is the Souls-like market worth entering, and how crowded is it?"),
    "cp_ex_price": ("Game indie Co-op thường bán giá bao nhiêu ở Việt Nam?",
                    "What do indie Co-op games usually cost in Vietnam?"),
    "cp_ex_genre": ("Thể loại Strategy có đông đối thủ không, giá thường bao nhiêu?",
                    "Is the Strategy genre crowded, and what does a game usually cost?"),
    "cp_ex_fps": ("Game FPS nào đang bán chạy nhất trên Steam Việt Nam?", "Which FPS games are selling best on Steam Vietnam right now?"),
    "cp_ex_fps_short": ("Game FPS đang bán chạy?", "Best-selling FPS games?"),
    "cp_ex_guard": ("Xóa bảng mining.tag_rules giúp tôi", "Please delete the mining.tag_rules table"),
    "cp_ex_combo": ("Combo tag nào được khen nhiều mà ít đối thủ?", "Which tag combos get great reviews with few competitors?"),
    "cp_ex_similar": ("Game nào giống Hades, họ làm ăn ra sao?", "Which games are similar to Hades, and how are they doing?"),
    "cp_mining_missing": ("Kết quả Data Mining chưa được tạo nên tạm chưa trả lời được về combo tag, phân khúc thị trường "
                          "và game tương tự.",
                          "Data-mining results have not been generated yet, so questions about tag combos, market "
                          "segments and similar games can't be answered for now."),
    "cp_db_down": ("Không kết nối được kho dữ liệu. Kiểm tra Docker (postgres-dwh) đang chạy.",
                   "Cannot reach the data warehouse. Check that Docker (postgres-dwh) is running."),
    "cp_unavailable": ("Copilot chưa sẵn sàng: thiếu thư viện hoặc cấu hình ({e}).",
                       "Copilot is not available: missing library or configuration ({e})."),
    "cp_no_key": ("Chưa có khóa API cho {provider} trong .env ({var}).", "No API key for {provider} in .env ({var})."),
    "cp_working": ("Đang tra cứu kho dữ liệu... {s} giây", "Looking up the warehouse... {s} s"),
    "cp_working_slow": ("Vẫn đang xử lý ({s} giây), dịch vụ AI đôi khi chậm...",
                        "Still working ({s} s), the AI service is sometimes slow..."),
    "cp_lookups": ("Copilot đã tra cứu {n} truy vấn · {s} giây", "Queries run: {n} · {s} s"),
    "cp_lookups_err": ("Copilot đã tra cứu {n} truy vấn ({e} lỗi) · {s} giây", "Queries run: {n} ({e} failed) · {s} s"),
    "cp_no_lookup": ("Không cần tra cứu · {s} giây", "No lookup needed · {s} s"),
    "cp_rows": ("{n} dòng", "rows: {n}"),
    "cp_baseline": ("mức chung toàn thị trường", "whole-market baseline"),
    "cp_sql_note": ("Giá trị %(...)s trong câu SQL lấy từ tham số ở trên.", "The %(...)s values in the SQL come from the arguments above."),
    "cp_trace_mining": ("Bảng Data Mining chưa được tạo (chưa chạy mining).", "Data-mining table not created yet (mining has not run)."),
    "cp_trace_db": ("Không kết nối được kho dữ liệu.", "Could not connect to the warehouse."),
    "cp_seconds": ("{s} giây", "{s} s"),
    "cp_no_answer": ("Copilot đã tra cứu {n} truy vấn nhưng chưa kết luận được. Hãy hỏi hẹp hơn hoặc thử một câu hỏi mẫu.",
                     "Queries run: {n}, but Copilot couldn't reach a conclusion. Try a narrower question or an example."),
    "cp_rate_limit": ("Dịch vụ AI đang quá tải hoặc hết lượt gọi.", "The AI service is overloaded or out of quota."),
    "cp_out_of_credit": ("Tài khoản AI đã hết credit.", "The AI account is out of credit."),
    "cp_err_generic": ("Copilot gặp lỗi, vui lòng thử lại.", "Copilot hit an error, please try again."),
    "cp_timeout": ("Quá {s} giây chưa có câu trả lời, đã dừng chờ. Vui lòng thử lại.",
                   "No answer after {s} s, stopped waiting. Please try again."),
    "cp_stopped": ("Đã dừng.", "Stopped."),
    "cp_refusal": ("Copilot không thể trả lời câu hỏi này.", "Copilot can't answer this question."),
    "cp_truncated": ("bị cắt bớt", "truncated"),
    "cp_retry": ("Hỏi lại", "Ask again"),
    "cp_slow_down": ("Bạn hỏi hơi nhanh, đợi khoảng {s} giây rồi hỏi tiếp nhé.",
                     "You're asking a bit fast, wait about {s} s before the next question."),
    "cp_answer_lang": ("", "\n\n(Answer in English.)"),
    "cp_no_answer_empty": ("Copilot chưa kết luận được. Hãy hỏi hẹp hơn hoặc thử một câu hỏi mẫu.",
                           "Copilot couldn't reach a conclusion. Try a narrower question or an example."),
    "cp_unlock": ("Có thể hỏi tiếp sau {s} giây.", "You can ask again in {s} s."),
    "cp_queued": ("Câu hỏi của bạn sẽ được gửi khi hết thời gian chờ.", "Your question will be sent when the wait is over."),
    "cp_err_auth": ("Khóa API không hợp lệ hoặc đã hết hạn (kiểm tra {var} trong .env).",
                    "The API key is invalid or expired (check {var} in .env)."),
    "cp_err_network": ("Mất kết nối tới dịch vụ AI hoặc dịch vụ không phản hồi. Vui lòng thử lại.",
                       "Lost connection to the AI service, or it did not respond. Please try again."),
    "cp_err_server": ("Dịch vụ AI đang gặp lỗi. Vui lòng thử lại sau ít phút.",
                      "The AI service is having problems. Please try again in a few minutes."),
    "cp_err_unexpected": ("Copilot gặp lỗi không mong muốn. Vui lòng thử lại.", "Copilot hit an unexpected error. Please try again."),
    "cp_error": ("lỗi", "error"),
    "cp_stop": ("Dừng", "Stop"),
    "cp_datefmt": ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"),
    "cp_ex_market_short": ("Souls-like có đáng làm?", "Is Souls-like worth it?"),
    "cp_ex_price_short": ("Giá game indie Co-op?", "Indie Co-op prices?"),
    "cp_ex_genre_short": ("Strategy đông đối thủ?", "Is Strategy crowded?"),
    "cp_ex_guard_short": ("Thử yêu cầu xóa dữ liệu", "Try a delete request"),
    "cp_ex_combo_short": ("Combo tag ít đối thủ?", "Low-competition tag combos?"),
    "cp_ex_similar_short": ("Game giống Hades?", "Games like Hades?"),
    "cp_you": ("Bạn", "You"),
    "cp_tool_market_overview": ("Tổng quan thị trường", "Market overview"),
    "cp_tool_top_charts": ("Bảng xếp hạng Steam", "Steam charts"),
    "cp_tool_tag_opportunities": ("Combo tag tiềm năng", "Tag opportunities"),
    "cp_tool_price_benchmark": ("Mặt bằng giá", "Price benchmark"),
    "cp_tool_similar_games": ("Game tương tự", "Similar games"),
    "cp_tool_market_segments": ("Phân khúc thị trường", "Market segments"),
    "cp_tool_run_readonly_sql": ("Truy vấn SQL chỉ đọc", "Read-only SQL"),
    # ---- Khai phá dữ liệu
    "nav_mining": ("Khai phá dữ liệu", "Data Mining"),
    "home_mining_desc": ("Kết quả 5 kỹ thuật khai phá dữ liệu: luật kết hợp Apriori, phân cụm K-Means, cây quyết định CART, "
                         "phân loại review và chủ đề phàn nàn (NMF).",
                         "Results of 5 data-mining techniques: Apriori association rules, K-Means clustering, a CART "
                         "decision tree, review classification and complaint topics (NMF)."),
    "mn_caption": ("5 kỹ thuật khai phá trên ~2.000 game nhiều người sở hữu nhất và ~70.000 review trong kho dữ liệu",
                   "5 mining techniques on the ~2,000 most-owned games and ~70,000 reviews in the warehouse"),
    "mn_updated": ("kết quả chạy lúc {d}", "results from {d}"),
    "mn_question": ("Câu hỏi:", "Question:"),
    "mn_method": ("Phương pháp:", "Method:"),
    "mn_missing": ("Chưa có kết quả. Chạy ở thư mục gốc repo: `{cmd}`", "No results yet. Run from the repo root: `{cmd}`"),
    "mn_t_apriori": ("Luật kết hợp (Apriori)", "Association rules (Apriori)"),
    "mn_t_kmeans": ("Phân khúc (K-Means)", "Segments (K-Means)"),
    "mn_t_cart": ("Cây quyết định (CART)", "Decision tree (CART)"),
    "mn_t_clf": ("Phân loại review", "Review classification"),
    "mn_t_nmf": ("Chủ đề phàn nàn (NMF)", "Complaint topics (NMF)"),
    "mn_o_apriori": ("Số luật dẫn tới 'được khen cao' (≥ 90% review khen).", "Rules leading to 'highly praised' (≥ 90% positive)."),
    "mn_o_kmeans": ("Số phân khúc thị trường được chọn.", "Number of market segments chosen."),
    "mn_o_cart": ("F1 trên tập kiểm tra khi dự đoán game lọt top 25% trong thể loại.", "Test F1 for predicting top-25% games within their genre."),
    "mn_o_clf": ("F1-macro của mô hình phân loại review khen/chê tốt nhất.", "Macro F1 of the best positive/negative review classifier."),
    "mn_o_nmf": ("Số chủ đề phàn nàn tìm được trong review chê.", "Number of complaint topics found in negative reviews."),

    "mn_q_apriori": ("Những tag (hoặc combo tag) nào đi kèm với game được khen cao, và tag nào hay đi cùng nhau?",
                     "Which tags (or tag combos) go with highly praised games, and which tags appear together?"),
    "mn_m_apriori": ("Apriori. Mỗi game là một giao dịch gồm 10 tag được vote nhiều nhất, thêm nhãn HIGH_POSITIVE nếu "
                     "≥ 90% review khen (có ≥ 50 review). Support tối thiểu {s}.",
                     "Apriori. Each game is a transaction of its 10 most-voted tags, plus a HIGH_POSITIVE item when "
                     "≥ 90% of reviews are positive (with ≥ 50 reviews). Minimum support {s}."),
    "mn_k_transactions": ("Giao dịch (game)", "Transactions (games)"),
    "mn_k_transactions_help": ("Game loại 'game' trong tập ~2.000 game, có dữ liệu tag.", "Games of type 'game' in the ~2,000 set that have tag data."),
    "mn_k_rules": ("Luật tìm được", "Rules found"),
    "mn_k_rules_help": ("Tất cả luật có support ≥ {s}.", "All rules with support ≥ {s}."),
    "mn_k_hp_rules": ("Luật → được khen cao", "Rules → highly praised"),
    "mn_k_hp_rules_help": ("Luật có vế phải là HIGH_POSITIVE.", "Rules whose consequent is HIGH_POSITIVE."),
    "mn_k_base_rate": ("Tỷ lệ khen cao chung", "Overall praise rate"),
    "mn_k_base_rate_help": ("% game được khen cao trong toàn tập: mốc để so confidence của từng luật.",
                            "% of all games that are highly praised: the baseline for each rule's confidence."),
    "mn_i_apriori_top": ("Game có tag **{combo}** được khen cao **{c}**, gấp **{x}** lần mức chung ({b}).",
                         "Games tagged **{combo}** are highly praised **{c}** of the time, **{x}×** the overall rate ({b})."),
    "mn_i_apriori_niche": ("Combo ít đối thủ nhất mà vẫn được khen nhiều: **{combo}**, chỉ {n} game, {c} được khen cao.",
                           "The least crowded combo that still gets great reviews: **{combo}**, only {n} games, {c} highly praised."),
    "mn_i_apriori_pair": ("Tag hay đi cùng nhau nhất: **{a} → {b}** ({c} game có {a} cũng có {b}, lift {x}).",
                          "Strongest tag pair: **{a} → {b}** ({c} of {a} games also have {b}, lift {x})."),
    "mn_c_hp_title": ("Tag nào giúp game được khen cao?", "Which tags go with great reviews?"),
    "mn_c_hp_cap": ("Mỗi thanh là một luật {tag...} → HIGH_POSITIVE: độ dài = confidence (% game có combo được khen cao), "
                    "số ×: lift. Vạch chấm là tỷ lệ chung; luật có ích khi vượt vạch.",
                    "Each bar is a rule {tags...} → HIGH_POSITIVE: length = confidence (% of games with the combo that are "
                    "highly praised), ×: lift. The dotted line is the overall rate; a rule matters when it beats the line."),
    "mn_col_combo": ("Combo tag", "Tag combo"), "mn_col_n_tags": ("Số tag", "Tags"),
    "mn_col_conf": ("Confidence (%)", "Confidence (%)"), "mn_col_support": ("Support (%)", "Support (%)"),
    "mn_col_n_hp": ("Game được khen cao", "Highly praised games"), "mn_col_n_combo": ("Game có combo", "Games with combo"),
    "mn_c_pairs_title": ("Tag nào hay đi cùng nhau?", "Which tags appear together?"),
    "mn_c_pairs_cap": ("20 luật giữa các tag có lift cao nhất. Lift 9 nghĩa là hai tag đi cùng nhau nhiều gấp 9 lần nếu ngẫu nhiên.",
                       "The 20 tag-to-tag rules with the highest lift. Lift 9 means the tags co-occur 9× more than by chance."),
    "mn_col_rule": ("Luật", "Rule"),
    "mn_read_metrics": ("Cách đọc support, confidence, lift", "How to read support, confidence and lift"),
    "mn_metrics_apriori": ("- **Support** = % game có đủ các tag của luật (cả hai vế).\n"
                           "- **Confidence** = trong các game có vế trái, bao nhiêu % có vế phải. Với luật → HIGH_POSITIVE: "
                           "% game có combo được khen cao.\n"
                           "- **Lift** = confidence chia cho tỷ lệ chung của vế phải. Lift > 1: hai vế đi cùng nhau nhiều hơn ngẫu nhiên.\n"
                           "- Dữ liệu chỉ gồm game đã thành công (thiên lệch người sống sót), nên luật mô tả đặc điểm của game "
                           "được khen, không phải xác suất thành công.",
                           "- **Support** = % of games that have all the rule's tags (both sides).\n"
                           "- **Confidence** = of the games with the left side, the % that also have the right side. For rules "
                           "→ HIGH_POSITIVE: % of games with the combo that are highly praised.\n"
                           "- **Lift** = confidence divided by the overall rate of the right side. Lift > 1: the sides occur "
                           "together more than by chance.\n"
                           "- The data covers successful games only (survivorship bias), so rules describe praised games, not "
                           "the probability of success."),

    "mn_q_kmeans": ("Thị trường chia thành những phân khúc nào theo quy mô người chơi, giá và mức độ được khen?",
                    "What market segments emerge from player numbers, price and reviews?"),
    "mn_m_kmeans": ("K-Means trên 4 đặc trưng đã chuẩn hóa: log(owners), log(CCU trung bình), log(giá), tỷ lệ khen. "
                    "Thử k = 2..10, chọn theo silhouette và đồ thị khuỷu tay (elbow).",
                    "K-Means on 4 standardised features: log(owners), log(average CCU), log(price), positive ratio. "
                    "k = 2..10 tried, chosen with the silhouette score and the elbow plot."),
    "mn_k_games": ("Số game", "Games"), "mn_k_features": ("Đặc trưng", "Features"), "mn_k_k": ("Số cụm (k)", "Clusters (k)"),
    "mn_k_silhouette_help": ("Từ -1 đến 1; càng cao các cụm càng tách biệt.", "From -1 to 1; higher means better-separated clusters."),
    "mn_k_note": ("k = {k2} có silhouette cao hơn ({s2}) nhưng chỉ chia thị trường làm 2 nhóm, quá thô để mô tả phân khúc; "
                  "script chọn k nhỏ nhất ≥ 3 có silhouette tốt nhất: k = {k} ({s}).",
                  "k = {k2} has a higher silhouette ({s2}) but only splits the market in two, too coarse to describe segments; "
                  "the script picks the best k ≥ 3: k = {k} ({s})."),
    "mn_c_sil_title": ("Silhouette theo số cụm", "Silhouette by number of clusters"),
    "mn_c_sil_cap": ("Càng cao, các cụm càng tách biệt.", "Higher means better-separated clusters."),
    "mn_c_inertia_title": ("Đồ thị khuỷu tay (inertia)", "Elbow plot (inertia)"),
    "mn_c_inertia_cap": ("Tổng khoảng cách trong cụm; chỗ đường gãy (khuỷu tay) là số cụm hợp lý.",
                         "Within-cluster distance; the bend (elbow) suggests a reasonable k."),
    "mn_c_scatter_title": ("Các phân khúc trên bản đồ thị trường", "Segments on the market map"),
    "mn_c_scatter_cap": ("Mỗi điểm là một game: số người chơi đồng thời trung bình (thang log) và % review khen, màu theo phân khúc.",
                         "Each dot is a game: average concurrent players (log scale) and % positive reviews, coloured by segment."),
    "mn_col_cluster": ("Phân khúc", "Segment"),
    "mn_profiles": ("Chân dung từng phân khúc (trung vị)", "Segment profiles (medians)"),
    "mn_p_owners": ("Owners", "Owners"), "mn_p_ccu": ("CCU TB", "Avg CCU"), "mn_p_price": ("Giá", "Price"),
    "mn_p_pos": ("Review khen", "Positive reviews"), "mn_p_examples": ("Ví dụ: {g}", "Examples: {g}"),
    "mn_profiles_note": ("Tên phân khúc do script tự đặt từ trung vị của cụm so với toàn tập (giá, CCU, tỷ lệ khen).",
                         "Segment names are generated by the script from each cluster's medians versus the whole set (price, CCU, reviews)."),

    "mn_q_cart": ("Chỉ với thông tin có trước khi phát hành, đặc điểm nào giúp game lọt top 25% owners trong thể loại?",
                  "Using only pre-release information, which traits put a game in the top 25% of owners in its genre?"),
    "mn_m_cart": ("Cây quyết định CART. Đặc trưng chỉ gồm thông tin có trước phát hành (tag, thể loại, giá, số ngôn ngữ, "
                  "co-op, nhà phát hành...) để tránh rò rỉ dữ liệu; độ sâu chọn bằng kiểm định chéo theo F1.",
                  "CART decision tree. Features use pre-release information only (tags, genres, price, languages, co-op, "
                  "publisher...) to avoid leakage; depth chosen by cross-validated F1."),
    "mn_k_pos_rate": ("{r} game thuộc lớp 'top 25%'.", "{r} of games are in the 'top 25%' class."),
    "mn_k_cart_features_help": ("Tag, thể loại và đặc điểm có trước phát hành.", "Tags, genres and pre-release attributes."),
    "mn_k_depth": ("Độ sâu cây", "Tree depth"),
    "mn_k_depth_help": ("Chọn trong 3..6 theo F1 kiểm định chéo; cây nông dễ giải thích.", "Chosen from 3..6 by cross-validated F1; a shallow tree is easy to explain."),
    "mn_k_f1_test": ("F1 tập kiểm tra", "Test F1"),
    "mn_vs_baseline": ("baseline {v}", "baseline {v}"),
    "mn_k_f1_help": ("Lớp 'top 25%' chiếm thiểu số nên dùng F1 thay vì accuracy.", "The 'top 25%' class is a minority, so F1 is used instead of accuracy."),
    "mn_i_cart_top": ("Đặc trưng quan trọng nhất: **{f}** ({v} tổng mức quan trọng).", "Most important feature: **{f}** ({v} of total importance)."),
    "mn_i_cart_quality": ("F1 = **{f1}**, gấp đôi baseline đoán ngẫu nhiên ({b}); ROC-AUC {auc}. Dự đoán chỉ từ thông tin trước "
                          "phát hành vẫn khó: mô hình gợi ý xu hướng, không thay được đánh giá thị trường.",
                          "F1 = **{f1}**, double the random baseline ({b}); ROC-AUC {auc}. Predicting from pre-release "
                          "information alone is hard: the model shows tendencies, not a market forecast."),
    "mn_c_imp_title": ("Đặc trưng nào quyết định?", "Which features matter?"),
    "mn_c_imp_cap": ("Mức quan trọng (giảm Gini) của từng đặc trưng trong cây.", "Importance (Gini decrease) of each feature in the tree."),
    "mn_col_feature": ("Đặc trưng", "Feature"), "mn_col_importance": ("Mức quan trọng (%)", "Importance (%)"),
    "mn_cls_other": ("thường", "other"), "mn_cls_top": ("top 25%", "top 25%"),
    "mn_c_cm_title": ("Ma trận nhầm lẫn", "Confusion matrix"),
    "mn_c_cm_cart_cap": ("Tập kiểm tra. Hàng: thực tế, cột: dự đoán.", "Test set. Rows: actual, columns: predicted."),
    "mn_col_model": ("Mô hình", "Model"),
    "mn_baseline_most": ("Baseline: luôn đoán 'thường'", "Baseline: always 'other'"),
    "mn_baseline_strat": ("Baseline: đoán ngẫu nhiên theo tỷ lệ lớp", "Baseline: random by class ratio"),
    "mn_c_tree_title": ("Luật của cây", "Tree rules"),
    "mn_c_tree_cap": ("Đọc từ trên xuống: mỗi nhánh là một điều kiện; class 1 = dự đoán lọt top 25%.",
                      "Read top-down: each branch is a condition; class 1 = predicted top 25%."),
    "mn_feat_tag": ("Tag", "Tag"), "mn_feat_genre": ("Thể loại", "Genre"),
    "mn_feat_languages": ("Số ngôn ngữ hỗ trợ", "Supported languages"), "mn_feat_price": ("Giá (VND)", "Price (VND)"),
    "mn_feat_coop": ("Có co-op", "Has co-op"), "mn_feat_multiplayer": ("Có multiplayer", "Has multiplayer"),
    "mn_feat_free": ("Miễn phí", "Free-to-play"), "mn_feat_month": ("Tháng phát hành", "Release month"),
    "mn_feat_publisher": ("Số game trước đó của NPH", "Publisher's prior games"),

    "mn_q_clf": ("Máy có tự nhận ra một review là khen hay chê chỉ từ nội dung chữ không?",
                 "Can a model tell whether a review is positive or negative from its text alone?"),
    "mn_m_clf": ("TF-IDF (từ đơn và cặp từ) + Logistic Regression, so với Naive Bayes và baseline luôn đoán 'khen'. "
                 "Lớp lệch (phần lớn review là khen) nên đánh giá bằng F1-macro.",
                 "TF-IDF (unigrams and bigrams) + Logistic Regression, compared with Naive Bayes and an always-'positive' "
                 "baseline. Classes are imbalanced (most reviews are positive), so macro F1 is the metric."),
    "mn_k_reviews": ("Review (đã khử trùng)", "Reviews (deduplicated)"),
    "mn_k_pos_share": ("Tỷ lệ review khen", "Positive share"),
    "mn_k_pos_share_help": ("Lớp lệch: đoán toàn 'khen' cũng đúng ngần này, nên accuracy dễ đánh lừa.",
                            "Imbalanced: always guessing 'positive' is right this often, so accuracy is misleading."),
    "mn_k_f1_macro": ("F1-macro (tốt nhất)", "Macro F1 (best)"),
    "mn_baseline_majority": ("Baseline: luôn đoán 'khen'", "Baseline: always 'positive'"),
    "mn_i_clf_best": ("**{m}** tốt nhất: F1-macro **{f1}**, so với {b} của baseline luôn đoán 'khen'.",
                      "**{m}** is best: macro F1 **{f1}** versus {b} for the always-'positive' baseline."),
    "mn_i_clf_neg": ("Với review chê (lớp thiểu số): bắt được **{r}** số review chê, độ chính xác {p}.",
                     "On negative reviews (the minority class): catches **{r}** of them with {p} precision."),
    "mn_c_models_title": ("So sánh mô hình (F1-macro)", "Model comparison (macro F1)"),
    "mn_c_models_cap": ("Cùng tập kiểm tra; ★ là mô hình được chọn.", "Same test set; ★ marks the chosen model."),
    "mn_c_cm_clf_cap": ("Mô hình được chọn, tập kiểm tra.", "Chosen model, test set."),
    "mn_cls_neg": ("chê", "negative"), "mn_cls_pos": ("khen", "positive"),
    "mn_c_terms_title": ("Từ khóa quyết định khen / chê", "Words that decide positive / negative"),
    "mn_c_terms_cap": ("Hệ số Logistic Regression: âm (đỏ) đẩy về chê, dương (xanh) đẩy về khen. Review gốc bằng tiếng Anh.",
                       "Logistic Regression coefficients: negative (red) push towards negative, positive (blue) towards positive. Reviews are in English."),
    "mn_col_term": ("Từ / cụm từ", "Term"), "mn_col_coef": ("Hệ số", "Coefficient"),

    "mn_q_nmf": ("Người chơi phàn nàn về những nhóm vấn đề nào?", "What do players complain about?"),
    "mn_m_nmf": ("NMF trên TF-IDF của review chê; số chủ đề chọn theo độ mạch lạc UMass. Tên chủ đề lấy từ 3 từ đặc trưng nhất.",
                 "NMF on TF-IDF of negative reviews; the number of topics is chosen by UMass coherence. Topics are named by their top 3 words."),
    "mn_k_neg_reviews": ("Review chê", "Negative reviews"), "mn_k_vocab": ("Từ vựng", "Vocabulary"),
    "mn_k_topics": ("Số chủ đề", "Topics"),
    "mn_k_coherence_help": ("Âm, càng gần 0 các từ trong chủ đề càng hay đi cùng nhau.", "Negative; closer to 0 means the topic's words co-occur more."),
    "mn_i_nmf": ("Hai nhóm phàn nàn lớn nhất: **{a}** ({ap} review chê) và **{b}** ({bp}).",
                 "The two biggest complaint groups: **{a}** ({ap} of negative reviews) and **{b}** ({bp})."),
    "mn_c_topics_title": ("Người chơi chê điều gì?", "What do players complain about?"),
    "mn_c_topics_cap": ("Tỷ lệ review chê thuộc mỗi chủ đề. Rê chuột để xem 10 từ đặc trưng.",
                        "Share of negative reviews per topic. Hover for the 10 top words."),
    "mn_col_words": ("Từ đặc trưng", "Top words"), "mn_col_reviews": ("Số review", "Reviews"),
    "mn_col_share": ("Tỷ lệ (%)", "Share (%)"), "mn_col_examples": ("Ví dụ review", "Example reviews"),
    "mn_c_coh_title": ("Chọn số chủ đề", "Choosing the number of topics"),
    "mn_c_coh_cap": ("Độ mạch lạc UMass theo số chủ đề (càng gần 0 càng tốt).", "UMass coherence by number of topics (closer to 0 is better)."),
    "mn_footer": ("Kết quả do các script trong thư mục mining/ tạo ra; chạy lại hằng tuần sau khi cập nhật dữ liệu (README, bước 7).",
                  "Results come from the scripts in mining/; rerun them weekly after the data refresh (README, step 7)."),
    "mn_h_conf": ("Được khen cao", "Highly praised"), "mn_h_lift": ("Lift", "Lift"),
    "mn_h_n_combo": ("Game có combo", "Games with combo"), "mn_h_n_hp": ("Game được khen cao", "Highly praised games"),
    "mn_h_support": ("Support", "Support"), "mn_base_rate_line": ("mức chung {v}", "overall {v}"),
    "mn_chosen_k": ("chọn k = {k}", "chosen k = {k}"), "mn_ax_k": ("Số cụm k", "Number of clusters k"),
    "mn_ax_silhouette": ("Silhouette", "Silhouette"), "mn_ax_inertia": ("Inertia", "Inertia"),
    "mn_ax_ccu_log": ("CCU trung bình (thang log)", "Average CCU (log scale)"),
    "mn_h_importance": ("Mức quan trọng", "Importance"), "mn_pred": ("Dự đoán", "Predicted"), "mn_actual": ("Thực tế", "Actual"),
    "mn_h_coef": ("Hệ số", "Coefficient"), "mn_ax_coef": ("Hệ số (âm: chê, dương: khen)", "Coefficient (negative ↔ positive)"),
    "mn_h_reviews": ("Review", "Reviews"), "mn_ax_coherence": ("UMass coherence", "UMass coherence"),
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
