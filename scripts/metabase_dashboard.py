"""Dựng dashboard Metabase "Steam Market — Smart Dashboard" bằng API (dashboard as code).

Chạy lại bao nhiêu lần cũng được: collection / question / dashboard được tìm theo tên rồi cập nhật.
Cần METABASE_API_KEY trong .env (Admin settings > Authentication > API keys).

    .venv\\Scripts\\python.exe scripts\\metabase_dashboard.py
"""
import json
import os
import secrets
from pathlib import Path

import requests
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
ENV = dotenv_values(ENV_FILE)
BASE = os.environ.get("METABASE_URL", "http://localhost:3000") + "/api"
DB_NAME = "Steam Market DWH"
COLLECTION = "Steam DWH"
STREAMLIT_COLLECTION = "Streamlit"   # sub-collection: question riêng cho Streamlit, cột snake_case cố định
DASHBOARD = "Steam Market — Smart Dashboard"

# Bảng màu đã kiểm định (skill dataviz, reference palette, nền sáng):
# một chuỗi dữ liệu -> slot 1; tăng/giảm -> cặp xanh dương / đỏ; nhiều chuỗi -> slot theo thứ tự cố định.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
BLUE, RED = "#2a78d6", "#e34948"
SEQ_LOW, SEQ_HIGH = "#eef4fd", "#3987e5"   # dải tuần tự một màu cho bảng tô nền

S = requests.Session()
S.headers["x-api-key"] = ENV["METABASE_API_KEY"]


def api(method, path, **kw):
    r = S.request(method, BASE + path, **kw)
    if not r.ok:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
    return r.json() if r.text else None


def col(name):
    """Khóa column_settings của Metabase cho cột của câu SQL."""
    return json.dumps(["name", name], ensure_ascii=False)


def vnd(name):
    return {col(name): {"suffix": " ₫", "decimals": 0}}


def native(db_id, sql):
    return {"type": "native", "native": {"query": sql.strip(), "template-tags": {}}, "database": db_id}


# ---------------------------------------------------------------- questions

TOP50_DAILY = """
SELECT p.full_date AS "Ngày", SUM(p.peak_ccu) AS "Tổng CCU đỉnh"
FROM dw.fact_daily_game_performance AS p
JOIN dw.fact_game_ranking_daily AS r ON r.game_id = p.game_id AND r.full_date = p.full_date
GROUP BY p.full_date
ORDER BY p.full_date
"""

UNIVERSE = "FROM marts.mart_mining_features WHERE is_in_universe AND app_type = 'game'"


def heatmap_sql():
    hours = ",\n  ".join(f'ROUND(MAX(v) FILTER (WHERE hour_vn = {h})) AS "{h}h"' for h in range(24))
    return f"""
WITH s AS (
  SELECT EXTRACT(ISODOW FROM snapshot_at_vn)::INT AS dow, hour_vn, AVG(concurrent_players) AS v
  FROM marts.mart_ccu_hourly_trend
  GROUP BY 1, 2
)
SELECT
  CASE dow WHEN 1 THEN 'Thứ 2' WHEN 2 THEN 'Thứ 3' WHEN 3 THEN 'Thứ 4' WHEN 4 THEN 'Thứ 5'
           WHEN 5 THEN 'Thứ 6' WHEN 6 THEN 'Thứ 7' ELSE 'Chủ nhật' END AS "Thứ",
  {hours}
FROM s
GROUP BY dow
ORDER BY dow
"""


def questions(db_id, top5_titles):
    """Danh sách question: (key, name, description, display, sql, visualization_settings)."""
    hour_cols = [f"{h}h" for h in range(24)]
    return [
        # ---- Tab Hôm nay
        ("k_ccu", "Tổng CCU đỉnh của top 50",
         "Tổng số người chơi đồng thời cao nhất trong ngày của 50 game hot nhất; so với ngày trước.",
         "smartscalar", TOP50_DAILY,
         {"graph.dimensions": ["Ngày"], "graph.metrics": ["Tổng CCU đỉnh"], "scalar.compact_primary_number": True}),
        ("k_games", "Game trong tập phân tích",
         "Số game (loại game) trong tập ~2.000 game nhiều người sở hữu nhất, cập nhật hằng tuần.",
         "scalar", f'SELECT COUNT(*) AS "Số game" {UNIVERSE}', {}),
        ("k_price", "Giá trung vị (game trả phí)",
         "Giá bán phổ biến trên Steam Việt Nam của game trả phí trong tập phân tích.",
         "scalar",
         f'SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_vnd) AS "Giá trung vị" {UNIVERSE} AND NOT is_free AND price_vnd > 0',
         {"column_settings": vnd("Giá trung vị")}),
        ("k_free", "Tỷ lệ game miễn phí",
         "Phần trăm game miễn phí (free-to-play) trong tập phân tích.",
         "scalar", f'SELECT AVG(CASE WHEN is_free THEN 1.0 ELSE 0 END) AS "Tỷ lệ miễn phí" {UNIVERSE}',
         {"column_settings": {col("Tỷ lệ miễn phí"): {"number_style": "percent", "decimals": 1}}}),
        ("k_discount", "Top 50 đang giảm giá ≥ 50%",
         "Số game trong top 50 đang giảm giá từ 50% trở lên.",
         "scalar",
         "SELECT COUNT(*) FILTER (WHERE is_deep_discount) AS \"Số game\" FROM marts.mart_daily_movers WHERE status <> 'dropped_out'",
         {}),
        ("c_top10", "Top 10 game theo CCU đỉnh",
         "Số người chơi đồng thời cao nhất trong ngày gần nhất đã đủ dữ liệu.",
         "row",
         'SELECT game_title AS "Game", peak_ccu AS "CCU đỉnh" FROM marts.mart_executive_overview ORDER BY peak_ccu DESC LIMIT 10',
         {"graph.dimensions": ["Game"], "graph.metrics": ["CCU đỉnh"],
          "series_settings": {"CCU đỉnh": {"color": BLUE}},
          "graph.show_values": True, "graph.label_value_formatting": "compact",
          "graph.x_axis.title_text": "", "graph.y_axis.title_text": ""}),
        ("c_movers", "Tăng / giảm CCU mạnh nhất so với hôm trước",
         "Thay đổi CCU đỉnh của game top 50 so với ngày liền trước (xanh: tăng, đỏ: giảm).",
         "row", """
WITH m AS (
  SELECT game_title, peak_ccu_change_pct AS pct FROM marts.mart_daily_movers WHERE peak_ccu_change_pct IS NOT NULL
), pick AS (
  (SELECT * FROM m ORDER BY pct DESC LIMIT 6)
  UNION
  (SELECT * FROM m ORDER BY pct ASC LIMIT 6)
)
SELECT game_title AS "Game",
       CASE WHEN pct > 0 THEN pct END AS "Tăng (%)",
       CASE WHEN pct < 0 THEN pct END AS "Giảm (%)"
FROM pick
ORDER BY pct DESC
""",
         {"graph.dimensions": ["Game"], "graph.metrics": ["Tăng (%)", "Giảm (%)"],
          "stackable.stack_type": "stacked",
          "series_settings": {"Tăng (%)": {"color": BLUE}, "Giảm (%)": {"color": RED}},
          "graph.show_values": True,
          "column_settings": {col("Tăng (%)"): {"suffix": "%"}, col("Giảm (%)"): {"suffix": "%"}},
          "graph.x_axis.title_text": "", "graph.y_axis.title_text": ""}),

        # ---- Tab Người chơi
        ("c_hourly", "CCU theo giờ của 5 game đông nhất (giờ VN, thang log)",
         "Số người chơi đồng thời đo mỗi giờ trong 7 ngày gần nhất. Thang log để game nhỏ không bị game lớn che mất.",
         "line", """
WITH top5 AS (
  SELECT game_id FROM marts.mart_executive_overview ORDER BY peak_ccu DESC LIMIT 5
)
SELECT DATE_TRUNC('hour', h.snapshot_at_vn) AS "Giờ (VN)", h.game_title AS "Game",
       MAX(h.concurrent_players) AS "Người chơi"
FROM marts.mart_ccu_hourly_trend AS h
JOIN top5 USING (game_id)
WHERE h.snapshot_at >= NOW() - INTERVAL '7 days'
GROUP BY 1, 2
ORDER BY 1
""",
         {"graph.dimensions": ["Giờ (VN)", "Game"], "graph.metrics": ["Người chơi"],
          "graph.y_axis.scale": "log",
          "series_settings": {t: {"color": SERIES[i]} for i, t in enumerate(top5_titles)},
          "graph.x_axis.title_text": "", "graph.y_axis.title_text": ""}),
        ("c_heatmap", "Người chơi online theo giờ và thứ (giờ VN)",
         "CCU trung bình mỗi game trong top 50, theo giờ trong ngày và thứ trong tuần. Màu càng đậm càng đông.",
         "table", heatmap_sql(),
         {"table.column_formatting": [{
             "id": 0, "type": "range", "columns": hour_cols, "colors": [SEQ_LOW, SEQ_HIGH],
             "min_type": None, "max_type": None, "highlight_row": False}],
          "column_settings": {col(c): {"number_style": "decimal", "decimals": 0, "compact": True} for c in hour_cols}}),

        # ---- Tab Thị trường
        ("c_opportunity", "Bản đồ cơ hội theo tag",
         "Mỗi bong bóng là một tag (≥ 20 game). Trái: ít đối thủ; trên: nhiều game được khen ≥ 90%; bong bóng to: nhiều người sở hữu. Góc trên-trái là các ngách tiềm năng.",
         "scatter", """
SELECT tag_name AS "Tag", n_games AS "Số game (mức cạnh tranh)",
       pct_high_positive AS "% game được khen ≥ 90%", avg_owners AS "Owners trung bình"
FROM marts.mart_market_by_tag
WHERE n_games >= 20
""",
         {"graph.dimensions": ["Số game (mức cạnh tranh)"], "graph.metrics": ["% game được khen ≥ 90%"],
          "scatter.bubble": "Owners trung bình", "graph.x_axis.scale": "log",
          "graph.tooltip_columns": [col("Tag"), col("Owners trung bình")],
          "series_settings": {"% game được khen ≥ 90%": {"color": BLUE}},
          "column_settings": {col("% game được khen ≥ 90%"): {"suffix": "%"}}}),
        ("c_price_vs_rating", "Giá bán và tỷ lệ được khen (game trả phí)",
         "Mỗi điểm là một game trả phí có ≥ 50 review. Giá cao không đồng nghĩa với được khen nhiều hơn.",
         "scatter", f"""
SELECT game_title AS "Game", price_vnd AS "Giá (VND)", ROUND((positive_ratio * 100)::NUMERIC, 1) AS "% review khen"
{UNIVERSE} AND NOT is_free AND price_vnd > 0 AND positive_ratio IS NOT NULL
""",
         {"graph.dimensions": ["Giá (VND)"], "graph.metrics": ["% review khen"],
          "graph.tooltip_columns": [col("Game")],
          "series_settings": {"% review khen": {"color": BLUE}},
          "column_settings": {**vnd("Giá (VND)"), col("% review khen"): {"suffix": "%"}}}),
        ("c_genres", "Thể loại: quy mô thị trường",
         "Số người sở hữu trung bình mỗi game theo thể loại (thể loại có ≥ 30 game). Rê chuột để xem số game, tỷ lệ khen, giá trung vị.",
         "row", """
SELECT genre_name AS "Thể loại", avg_owners AS "Owners trung bình / game", n_games AS "Số game",
       ROUND(avg_positive_ratio * 100, 1) AS "% khen trung bình", median_price_vnd AS "Giá trung vị"
FROM marts.mart_market_by_genre
WHERE n_games >= 30
ORDER BY avg_owners DESC
LIMIT 12
""",
         {"graph.dimensions": ["Thể loại"], "graph.metrics": ["Owners trung bình / game"],
          "graph.tooltip_columns": [col("Số game"), col("% khen trung bình"), col("Giá trung vị")],
          "series_settings": {"Owners trung bình / game": {"color": BLUE}},
          "graph.show_values": True, "graph.label_value_formatting": "compact",
          "column_settings": {**vnd("Giá trung vị"), col("% khen trung bình"): {"suffix": "%"}},
          "graph.x_axis.title_text": "", "graph.y_axis.title_text": ""}),
        ("c_price_box", "Phân bố giá theo thể loại (game trả phí)",
         "Hộp: 50% game ở giữa; vạch: giá trung vị; chấm: game giá bất thường. 8 thể loại nhiều game nhất.",
         "boxplot", f"""
WITH top_genres AS (
  -- "Free To Play" gần như không có game trả phí nên không có ý nghĩa với phân bố giá
  SELECT genre_name FROM marts.mart_market_by_genre
  WHERE genre_name <> 'Free To Play'
  ORDER BY n_games DESC LIMIT 8
)
SELECT g.genre_name AS "Thể loại", f.price_vnd AS "Giá (VND)"
FROM marts.mart_mining_features AS f
JOIN dw.bridge_game_genre AS b ON b.game_id = f.game_id
JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
JOIN top_genres AS t ON t.genre_name = g.genre_name
WHERE f.is_in_universe AND f.app_type = 'game' AND NOT f.is_free AND f.price_vnd > 0
""",
         {"graph.dimensions": ["Thể loại"], "graph.metrics": ["Giá (VND)"],
          "boxplot.points_mode": "outliers", "boxplot.show_values_mode": "median", "boxplot.show_mean": False,
          "series_settings": {"Giá (VND)": {"color": BLUE}},
          "graph.x_axis.title_text": "", "graph.y_axis.title_text": "",
          "column_settings": vnd("Giá (VND)")}),
        ("c_discounts", "Game đang giảm giá sâu (≥ 50%)",
         "Các game có nhiều người sở hữu nhất đang giảm giá từ 50% trở lên, theo giá Steam Việt Nam.",
         "table", """
SELECT d.game_title AS "Game", d.price_initial_vnd AS "Giá gốc", d.price_vnd AS "Giá sau giảm",
       d.discount_pct AS "% giảm", f.owners_mid AS "Owners"
FROM dw.dim_game AS d
JOIN marts.mart_mining_features AS f USING (game_id)
WHERE d.valid_to IS NULL AND d.discount_pct >= 50 AND d.price_vnd IS NOT NULL
ORDER BY f.owners_mid DESC NULLS LAST, d.discount_pct DESC
LIMIT 15
""",
         {"table.column_formatting": [{
             "id": 0, "type": "range", "columns": ["% giảm"], "colors": [SEQ_LOW, SEQ_HIGH],
             "min_type": None, "max_type": None, "highlight_row": False}],
          "column_settings": {**vnd("Giá gốc"), **vnd("Giá sau giảm"),
                              col("% giảm"): {"suffix": "%"},
                              col("Owners"): {"compact": True}}}),
    ]


# ---------------------------------------------------------------- question cho Streamlit
# Streamlit lấy số liệu qua Metabase API rồi tự vẽ bằng Plotly. Tên cột là "hợp đồng" với code
# dashboard/: đổi tên cột ở đây thì phải sửa dashboard/views/smart_dashboard.py theo.

def streamlit_questions():
    return [
        ("[Streamlit] KPI CCU theo ngày", """
SELECT p.full_date AS full_date, SUM(p.peak_ccu) AS total_peak_ccu
FROM dw.fact_daily_game_performance AS p
JOIN dw.fact_game_ranking_daily AS r ON r.game_id = p.game_id AND r.full_date = p.full_date
GROUP BY p.full_date
ORDER BY p.full_date
"""),
        ("[Streamlit] KPI thị trường", f"""
SELECT
  COUNT(*) AS n_games,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_vnd) FILTER (WHERE NOT is_free AND price_vnd > 0) AS median_price_vnd,
  AVG(CASE WHEN is_free THEN 1.0 ELSE 0 END) AS pct_free,
  (SELECT COUNT(*) FILTER (WHERE is_deep_discount) FROM marts.mart_daily_movers WHERE status <> 'dropped_out') AS n_deep_discount
{UNIVERSE}
"""),
        ("[Streamlit] Top 50 hôm nay", """
SELECT full_date, ranking_order, game_id, game_title, genres, is_free, price_vnd, discount_pct, peak_ccu, avg_ccu
FROM marts.mart_executive_overview
ORDER BY peak_ccu DESC
"""),
        ("[Streamlit] Biến động top 50", """
SELECT report_date, game_id, game_title, status, rank_today, rank_yesterday, peak_ccu_today, peak_ccu_yesterday,
       peak_ccu_change_pct, snapshots_today, snapshots_yesterday, discount_pct
FROM marts.mart_daily_movers
"""),
        ("[Streamlit] CCU theo giờ (top 50, 7 ngày)", """
SELECT game_id, game_title, snapshot_at_vn, concurrent_players
FROM marts.mart_ccu_hourly_trend
WHERE snapshot_at >= NOW() - INTERVAL '7 days'
ORDER BY snapshot_at_vn
"""),
        ("[Streamlit] CCU theo giờ và thứ", """
SELECT EXTRACT(ISODOW FROM snapshot_at_vn)::INT AS dow, hour_vn,
       AVG(concurrent_players) AS avg_ccu, COUNT(DISTINCT snapshot_at_vn::DATE) AS n_days
FROM marts.mart_ccu_hourly_trend
GROUP BY 1, 2
"""),
        ("[Streamlit] Thị trường theo tag", """
SELECT tag_name, n_games, pct_high_positive, avg_owners, avg_positive_ratio, median_price_vnd
FROM marts.mart_market_by_tag
WHERE n_games >= 20
"""),
        ("[Streamlit] Thị trường theo thể loại", """
SELECT genre_name, n_games, avg_owners, avg_positive_ratio, pct_high_positive, median_price_vnd, pct_free
FROM marts.mart_market_by_genre
WHERE n_games >= 10
"""),
        ("[Streamlit] Giá và tỷ lệ khen", f"""
SELECT game_title, price_vnd, (positive_ratio * 100)::NUMERIC(5, 1) AS positive_pct, owners_mid
{UNIVERSE} AND NOT is_free AND price_vnd > 0 AND positive_ratio IS NOT NULL
"""),
        ("[Streamlit] Giá theo thể loại", """
WITH top_genres AS (
  SELECT genre_name FROM marts.mart_market_by_genre
  WHERE genre_name <> 'Free To Play'
  ORDER BY n_games DESC LIMIT 8
)
SELECT g.genre_name, f.price_vnd
FROM marts.mart_mining_features AS f
JOIN dw.bridge_game_genre AS b ON b.game_id = f.game_id
JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
JOIN top_genres AS t ON t.genre_name = g.genre_name
WHERE f.is_in_universe AND f.app_type = 'game' AND NOT f.is_free AND f.price_vnd > 0
"""),
        ("[Streamlit] Game giảm giá sâu", """
SELECT d.game_title, d.price_initial_vnd, d.price_vnd, d.discount_pct, f.owners_mid
FROM dw.dim_game AS d
JOIN marts.mart_mining_features AS f USING (game_id)
WHERE d.valid_to IS NULL AND d.discount_pct >= 50 AND d.price_vnd IS NOT NULL
ORDER BY f.owners_mid DESC NULLS LAST, d.discount_pct DESC
LIMIT 12
"""),
    ]


def enable_embedding(dash_id):
    """Bật static embedding cho dashboard để Streamlit nhúng (iframe có ký JWT)."""
    secret = ENV.get("METABASE_EMBED_SECRET")
    if not secret:
        secret = secrets.token_hex(32)
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n# Metabase static embedding (scripts/metabase_dashboard.py)\nMETABASE_EMBED_SECRET={secret}\n")
        print("  đã sinh METABASE_EMBED_SECRET và lưu vào .env")
    api("PUT", "/setting/embedding-secret-key", json={"value": secret})
    api("PUT", "/setting/enable-embedding-static", json={"value": True})
    api("PUT", f"/dashboard/{dash_id}", json={"enable_embedding": True, "embedding_params": {}})


def get_or_create_collection(name, parent_id=None):
    for c in api("GET", "/collection"):
        if c["name"] == name and (c.get("location") or "/") == (f"/{parent_id}/" if parent_id else "/"):
            return c["id"]
    return api("POST", "/collection", json={"name": name, "color": "#2a78d6", "parent_id": parent_id})["id"]


def upsert_cards(coll_id, items):
    """items: [(name, description, display, dataset_query, viz)] -> {name: id}"""
    existing = {c["name"]: c["id"] for c in api("GET", f"/collection/{coll_id}/items", params={"models": "card"})["data"]}
    ids = {}
    for name, desc, display, query, viz in items:
        body = {"name": name, "description": desc, "display": display, "collection_id": coll_id,
                "dataset_query": query, "visualization_settings": viz}
        card = api("PUT", f"/card/{existing[name]}", json=body) if name in existing else api("POST", "/card", json=body)
        ids[name] = card["id"]
        print(f"  question {card['id']:>4}  {name}")
    return ids


# ---------------------------------------------------------------- dashboard layout (lưới 24 cột)

def text_card(text, display="text"):
    return {"card_id": None, "series": [], "parameter_mappings": [],
            "visualization_settings": {
                "virtual_card": {"name": None, "display": display, "visualization_settings": {},
                                 "dataset_query": {}, "archived": False},
                "text": text, "dashcard.background": False}}


TABS = [{"id": -1, "name": "Hôm nay"}, {"id": -2, "name": "Người chơi"}, {"id": -3, "name": "Thị trường"}]

LAYOUT = [
    # (tab, key hoặc ("heading"/"text", nội dung), row, col, w, h)
    (-1, ("heading", "Thị trường Steam hôm nay"), 0, 0, 24, 1),
    (-1, ("text", "Số liệu của **ngày gần nhất đã đủ dữ liệu** (UTC). Top 50 lấy từ SteamSpy; CCU đo mỗi giờ."), 1, 0, 24, 1),
    (-1, "k_ccu", 2, 0, 5, 3),
    (-1, "k_games", 2, 5, 5, 3),
    (-1, "k_price", 2, 10, 5, 3),
    (-1, "k_free", 2, 15, 4, 3),
    (-1, "k_discount", 2, 19, 5, 3),
    (-1, "c_top10", 5, 0, 12, 9),
    (-1, "c_movers", 5, 12, 12, 9),

    (-2, ("heading", "Người chơi online lúc nào?"), 0, 0, 24, 1),
    (-2, ("text", "Giờ hiển thị theo **giờ Việt Nam**. Khoảng trống trên biểu đồ là giờ máy chủ thu thập không chạy."), 1, 0, 24, 1),
    (-2, "c_hourly", 2, 0, 24, 9),
    (-2, "c_heatmap", 11, 0, 24, 6),

    (-3, ("heading", "Thị trường ~2.000 game nhiều người sở hữu nhất"), 0, 0, 24, 1),
    (-3, ("text", "Dữ liệu cập nhật hằng tuần. Owners là khoảng ước lượng của SteamSpy; giá theo Steam Việt Nam."), 1, 0, 24, 1),
    (-3, "c_opportunity", 2, 0, 24, 10),
    (-3, "c_price_vs_rating", 12, 0, 12, 9),
    (-3, "c_genres", 12, 12, 12, 9),
    (-3, "c_price_box", 21, 0, 12, 9),
    (-3, "c_discounts", 21, 12, 12, 9),
]


def main():
    db_id = next(d["id"] for d in api("GET", "/database")["data"] if d["name"] == DB_NAME)

    # Mặc định Metabase chỉ lấy 2.000 dòng cho truy vấn SQL; box plot cần toàn bộ giá trị (~3.500 dòng)
    api("PUT", "/setting/unaggregated-query-row-limit", json={"value": 10000})

    coll_id = get_or_create_collection(COLLECTION)

    # Tên 5 game đông nhất hiện tại, để gán màu cố định cho từng game trên biểu đồ đường
    probe = api("POST", "/dataset", json=native(
        db_id, "SELECT game_title FROM marts.mart_executive_overview ORDER BY peak_ccu DESC LIMIT 5"))
    top5 = [row[0] for row in probe["data"]["rows"]]

    qs = questions(db_id, top5)
    by_name = upsert_cards(coll_id, [(name, desc, display, native(db_id, sql), viz)
                                     for _key, name, desc, display, sql, viz in qs])
    card_ids = {key: by_name[name] for key, name, *_ in qs}

    st_coll_id = get_or_create_collection(STREAMLIT_COLLECTION, parent_id=coll_id)
    upsert_cards(st_coll_id, [(name, "Dùng cho Streamlit (dashboard/). Đừng đổi tên cột.", "table",
                               native(db_id, sql), {}) for name, sql in streamlit_questions()])

    dash = next((d for d in api("GET", f"/collection/{coll_id}/items", params={"models": "dashboard"})["data"]
                 if d["name"] == DASHBOARD), None)
    if dash is None:
        dash = api("POST", "/dashboard", json={"name": DASHBOARD, "collection_id": coll_id,
                                               "description": "Dashboard thị trường game Steam - dựng bằng scripts/metabase_dashboard.py"})
    dash_id = dash["id"]

    dashcards = []
    for i, (tab, item, row, c, w, h) in enumerate(LAYOUT, start=1):
        base = {"id": -i, "dashboard_tab_id": tab, "row": row, "col": c, "size_x": w, "size_y": h}
        if isinstance(item, tuple):
            dashcards.append({**base, **text_card(item[1], item[0])})
        else:
            dashcards.append({**base, "card_id": card_ids[item], "series": [], "parameter_mappings": [],
                              "visualization_settings": {}})
    api("PUT", f"/dashboard/{dash_id}", json={"tabs": TABS, "dashcards": dashcards, "width": "full"})
    enable_embedding(dash_id)
    print(f"\nDashboard {dash_id}: {BASE.removesuffix('/api')}/dashboard/{dash_id} (đã bật nhúng)")


if __name__ == "__main__":
    main()
