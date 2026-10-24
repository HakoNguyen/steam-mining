"""
Công cụ tra cứu của Copilot (chức năng 3: trợ lý khảo sát thị trường). Mỗi công cụ là 1 hàm Python thuần chạy SQL
cố định trên warehouse bằng user chỉ-đọc copilot_ro; llm.py đăng ký các hàm này làm tool cho AI.
Mỗi câu SQL đã chạy được ghi vào trace để giao diện hiện mục "Copilot đã tra cứu gì".

Cần chạy mining trước (mining/association_rules.py, mining/kmeans_clustering.py) để có mining.tag_rules, mining.game_clusters.
"""
import functools
import json
import os
import re
import socket
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2.extras import RealDictCursor

# Giá trị trong .env thắng biến môi trường: VS Code nạp .env vào terminal lúc mở và nhớ bản cũ, nên sửa .env
# (đổi COPILOT_PROVIDER, khóa API) rồi chạy lại vẫn bị bản cũ ghi đè. Không có .env (Docker) thì dùng os.environ.
ENV = {**os.environ, **{k: v for k, v in dotenv_values(Path(__file__).resolve().parents[2] / ".env").items() if v}}
UNIVERSE = "f.is_in_universe AND f.app_type = 'game'"
MAX_ROWS = 50
_trace = ContextVar("copilot_trace", default=None)


def _norm_sql(column):
    """So tên tag/thể loại bỏ hoa thường, dấu cách, gạch nối: "roguelike" khớp "Rogue-like"."""
    return f"REGEXP_REPLACE(LOWER({column}), '[^a-z0-9]', '', 'g')"


def _norm(names):
    return sorted({re.sub(r"[^a-z0-9]", "", n.lower()) for n in names})


@contextmanager
def tracing():
    """with tracing() as trace: ... -> trace là list các {tool, args, sql, n_rows | error} đã chạy trong khối."""
    trace = []
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        _trace.reset(token)


@functools.cache
def _db_address():
    """Host/port chỉ lấy từ biến môi trường (Docker đặt postgres-dwh:5432); chạy trên máy thì localhost:5433.
    VS Code tự nạp .env (POSTGRES_HOST=postgres-dwh, tên chỉ có trong mạng Docker) vào terminal, nên tên máy không
    phân giải được thì hiểu là đang chạy ngoài Docker và dùng localhost:5433."""
    host, port = os.environ.get("POSTGRES_HOST", "localhost"), os.environ.get("POSTGRES_PORT", "5433")
    try:
        socket.getaddrinfo(host, None)
    except socket.gaierror:
        return "localhost", "5433"
    return host, port


def _connect():
    # Quyền chỉ-đọc + timeout 5s do role copilot_ro đảm bảo ở phía DB.
    host, port = _db_address()
    conn = psycopg2.connect(host=host, port=port,
                            dbname=ENV.get("POSTGRES_DB", "steam_dwh"), user=ENV.get("COPILOT_DB_USER", "copilot_ro"),
                            password=ENV.get("COPILOT_DB_PASSWORD"), cursor_factory=RealDictCursor)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def _query(tool, args, sql, params=None):
    entry = {"tool": tool, "args": args, "sql": sql.strip()}
    if (trace := _trace.get()) is not None:
        trace.append(entry)
    try:
        conn = _connect()
    except psycopg2.Error as e:  # ghi vào trace để giao diện hiện đúng lỗi kết nối
        entry["error"] = f"Không kết nối được database: {str(e).strip()}"
        raise
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [{k: float(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in cur.fetchall()]
    except psycopg2.Error as e:
        entry["error"] = str(e).strip()
        raise
    finally:
        conn.close()
    entry["n_rows"] = len(rows)
    return rows


def _exists(table):
    """Bảng có tồn tại không (vd. mining.* chỉ có sau khi chạy script mining); không ghi vào trace."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) IS NOT NULL AS ok", (table,))
            return cur.fetchone()["ok"]
    finally:
        conn.close()


def _require_mining(table):
    if not _exists(table):
        raise ValueError(f"Warehouse chưa có kết quả khai phá dữ liệu ({table}): chưa chạy script mining. "
                         "Đừng gọi lại công cụ này; trả lời bằng market_overview / price_benchmark và nói rõ phần còn thiếu.")


def _json(data):
    return json.dumps(data, ensure_ascii=False, default=str)


def _find_game(tool, name):
    rows = _query(tool, {"game_name": name}, """
        SELECT game_id, game_title FROM marts.mart_mining_features
        WHERE game_title ILIKE %(pattern)s
        ORDER BY LOWER(game_title) = LOWER(%(name)s) DESC, owners_mid DESC NULLS LAST
        LIMIT 5
    """, {"name": name, "pattern": f"%{name}%"})
    if not rows:
        raise ValueError(f"Không tìm thấy game nào tên giống '{name}' trong warehouse (~2.000 game nhiều người sở hữu nhất).")
    return rows[0], [r["game_title"] for r in rows[1:]]


def _baseline(tool):
    return _query(tool, {}, f"""
        SELECT COUNT(*) AS n_games,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.owners_mid) AS median_owners,
               ROUND(AVG(f.positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
               ROUND(100.0 * AVG(f.is_high_positive::INT), 1) AS pct_high_positive,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.price_vnd) FILTER (WHERE NOT f.is_free AND f.price_vnd > 0)
                 AS median_price_vnd,
               ROUND(100.0 * AVG(f.is_free::INT), 1) AS pct_free,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.avg_ccu) AS median_ccu
        FROM marts.mart_mining_features AS f
        WHERE {UNIVERSE}
    """)[0]


def market_overview(tag: str | None = None, genre: str | None = None, limit: int = 10) -> str:
    """Tổng quan thị trường theo tag hoặc thể loại: số game (mức cạnh tranh), owners, tỷ lệ khen, giá trung vị, % miễn phí, CCU.
    Luôn kèm số liệu toàn thị trường (baseline) để so sánh. Không truyền tag/genre thì trả về các tag nhiều game nhất.

    Args:
        tag: Tên tag Steam bằng tiếng Anh, ví dụ "Roguelike", "Souls-like", "Co-op".
        genre: Tên thể loại Steam bằng tiếng Anh, ví dụ "RPG", "Strategy", "Simulation".
        limit: Số dòng tối đa khi liệt kê hoặc gợi ý tên gần đúng.
    """
    args = {"tag": tag, "genre": genre, "limit": limit}
    limit = min(limit, MAX_ROWS)
    tables = {"genre": ("marts.mart_market_by_genre", "genre_name"), "tag": ("marts.mart_market_by_tag", "tag_name")}
    kind, value = ("genre", genre) if genre else ("tag", tag)
    if value:
        # khớp đúng (nếu có) đứng đầu, kèm các tên chứa từ khóa (biến thể như Rogue-lite, Action Roguelike).
        # Không thấy thì thử loại còn lại: nhiều tên vừa giống thể loại vừa là tag (vd. "Survival" là tag, không phải thể loại).
        v = _norm([value])[0]
        for k in (kind, "tag" if kind == "genre" else "genre"):
            table, key = tables[k]
            rows = _query("market_overview", args, f"""
                SELECT * FROM {table} WHERE {_norm_sql(key)} LIKE %(p)s
                ORDER BY {_norm_sql(key)} = %(v)s DESC, n_games DESC LIMIT %(n)s
            """, {"v": v, "p": f"%{v}%", "n": limit})
            if rows:
                break
        exact = bool(rows) and _norm([rows[0][key]])[0] == v
        result = {"matched_as": k, "market": rows[0] if exact else None, "related": rows[1:] if exact else rows}
    else:
        result = {"top_by_n_games": _query("market_overview", args,
                                           f"SELECT * FROM {table} ORDER BY n_games DESC LIMIT %(n)s", {"n": limit})}
    result["baseline_all_games"] = _baseline("market_overview")
    return _json(result)


def tag_opportunities(tags: list[str] | None = None, max_games: int | None = None, limit: int = 10) -> str:
    """Combo tag "được khen nhiều mà ít đối thủ": luật kết hợp Apriori {tag...} -> HIGH_POSITIVE (>= 90% review khen).
    confidence = tỷ lệ game có combo này được khen cao; lift = gấp bao nhiêu lần tỷ lệ chung;
    n_games_with_combo = số game có combo (mức cạnh tranh, đối thủ); n_games_highly_praised = trong đó số game được khen cao.

    Args:
        tags: Chỉ lấy combo có chứa TẤT CẢ các tag này (tiếng Anh), ví dụ ["Roguelike"]. Bỏ trống để xem mọi combo.
        max_games: Chỉ lấy combo có tối đa ngần này game có combo (ít đối thủ).
        limit: Số combo trả về.
    """
    args = {"tags": tags, "max_games": max_games, "limit": limit}
    _require_mining("mining.tag_rules")
    # mining.tag_rules.n_games = số game có combo (vế trái); số game được khen cao = n_games * confidence
    rows = _query("tag_opportunities", args, f"""
        SELECT antecedents AS tags, n_games AS n_games_with_combo,
               ROUND(n_games * confidence)::INT AS n_games_highly_praised, ROUND(confidence::NUMERIC, 3) AS confidence,
               ROUND(lift::NUMERIC, 2) AS lift
        FROM mining.tag_rules
        WHERE is_high_positive
          AND (CAST(%(tags)s AS TEXT[]) IS NULL
               OR (SELECT ARRAY_AGG({_norm_sql("a")}) FROM UNNEST(antecedents) AS a) @> CAST(%(tags)s AS TEXT[]))
          AND (%(max_games)s IS NULL OR n_games <= %(max_games)s)
        ORDER BY lift DESC, n_games_with_combo
        LIMIT %(n)s
    """, {"tags": _norm(tags) if tags else None, "max_games": max_games, "n": min(limit, MAX_ROWS)})
    base = _baseline("tag_opportunities")
    return _json({"combos": rows, "base_rate_high_positive_pct": base["pct_high_positive"], "n_games_total": base["n_games"]})


def price_benchmark(tags: list[str] | None = None, genre: str | None = None) -> str:
    """Mặt bằng giá (VND) của game trả phí có cùng tag/thể loại: số game, giá p25/trung vị/p75, % miễn phí,
    và theo từng khoảng giá: số game, tỷ lệ khen trung bình, owners trung vị (để thấy khoảng giá nào được đón nhận tốt).

    Args:
        tags: Game phải có TẤT CẢ các tag này trong 10 tag đặc trưng (tiếng Anh), ví dụ ["Indie", "Co-op"].
        genre: Thể loại (tiếng Anh), ví dụ "RPG".
    """
    args = {"tags": tags, "genre": genre}
    scope = f"""
        tagged AS (
          SELECT b.game_id FROM dw.bridge_game_tag AS b JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
          WHERE b.vote_rank <= 10 AND {_norm_sql("t.tag_name")} = ANY(CAST(%(tags)s AS TEXT[]))
          GROUP BY b.game_id
          HAVING COUNT(DISTINCT {_norm_sql("t.tag_name")}) = CARDINALITY(CAST(%(tags)s AS TEXT[]))
        ), genred AS (
          SELECT b.game_id FROM dw.bridge_game_genre AS b JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
          WHERE {_norm_sql("g.genre_name")} = %(genre)s
        ), s AS (
          SELECT f.* FROM marts.mart_mining_features AS f
          WHERE {UNIVERSE}
            AND (CAST(%(tags)s AS TEXT[]) IS NULL OR f.game_id IN (SELECT game_id FROM tagged))
            AND (CAST(%(genre)s AS TEXT) IS NULL OR f.game_id IN (SELECT game_id FROM genred))
        )
    """
    params = {"tags": _norm(tags) if tags else None, "genre": _norm([genre])[0] if genre else None}
    summary = _query("price_benchmark", args, f"""
        WITH {scope}
        SELECT COUNT(*) AS n_games, ROUND(100.0 * AVG(is_free::INT), 1) AS pct_free,
               COUNT(*) FILTER (WHERE NOT is_free AND price_vnd > 0) AS n_paid_with_vn_price,
               PERCENTILE_CONT(ARRAY[0.25, 0.5, 0.75]) WITHIN GROUP (ORDER BY price_vnd)
                 FILTER (WHERE NOT is_free AND price_vnd > 0) AS price_p25_p50_p75
        FROM s
    """, params)[0]
    bands = _query("price_benchmark", args, f"""
        WITH {scope}
        SELECT CASE WHEN price_vnd < 100000 THEN '1. < 100k' WHEN price_vnd < 250000 THEN '2. 100k-250k'
                    WHEN price_vnd < 500000 THEN '3. 250k-500k' ELSE '4. >= 500k' END AS price_band,
               COUNT(*) AS n_games, ROUND(AVG(positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY owners_mid) AS median_owners
        FROM s WHERE NOT is_free AND price_vnd > 0
        GROUP BY 1 ORDER BY 1
    """, params)
    return _json({"summary": summary, "by_price_band": bands})


def similar_games(game_name: str | None = None, tags: list[str] | None = None, limit: int = 10) -> str:
    """Game giống nhất theo 10 tag đặc trưng (xếp theo số tag trùng, rồi Jaccard), kèm owners, tỷ lệ khen, giá, CCU và phân khúc K-Means.
    Dùng cho "ý tưởng của tôi giống game nào / làm ăn ra sao" (truyền tags) hoặc "gợi ý game giống X" (truyền game_name).

    Args:
        game_name: Tên game gốc (tìm gần đúng), ví dụ "Hades".
        tags: Danh sách tag (tiếng Anh) mô tả ý tưởng, ví dụ ["Roguelike", "Action", "Pixel Graphics"].
        limit: Số game trả về.
    """
    args = {"game_name": game_name, "tags": tags, "limit": limit}
    target, exclude, others = None, None, []
    if game_name:
        target, others = _find_game("similar_games", game_name)
        exclude = target["game_id"]
        tags = [r["tag_name"] for r in _query("similar_games", args, """
            SELECT t.tag_name FROM dw.bridge_game_tag AS b JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
            WHERE b.game_id = %(id)s AND b.vote_rank <= 10 ORDER BY b.vote_rank
        """, {"id": exclude})]
    if not tags:
        raise ValueError("Cần game_name (game có dữ liệu tag) hoặc danh sách tags.")
    clusters = _exists("mining.game_clusters")
    rows = _query("similar_games", args, f"""
        WITH target AS (SELECT UNNEST(CAST(%(tags)s AS TEXT[])) AS tag),
        score AS (
          SELECT b.game_id, COUNT(*) AS n_tags, COUNT(target.tag) AS shared,
                 ARRAY_AGG(t.tag_name ORDER BY b.vote_rank) FILTER (WHERE target.tag IS NOT NULL) AS shared_tags
          FROM dw.bridge_game_tag AS b
          JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
          LEFT JOIN target ON target.tag = {_norm_sql("t.tag_name")}
          WHERE b.vote_rank <= 10
          GROUP BY b.game_id
        )
        SELECT f.game_title, s.shared_tags,
               ROUND(s.shared::NUMERIC / (s.n_tags + (SELECT COUNT(*) FROM target) - s.shared), 3) AS jaccard,
               f.owners_min, f.owners_max, f.positive_ratio, f.total_reviews, f.is_free, f.price_vnd, f.avg_ccu,
               f.release_date, {"c.cluster_label" if clusters else "NULL AS cluster_label"}
        FROM score AS s
        JOIN marts.mart_mining_features AS f ON f.game_id = s.game_id
        {"LEFT JOIN mining.game_clusters AS c ON c.game_id = s.game_id" if clusters else ""}
        WHERE s.shared > 0 AND {UNIVERSE} AND f.game_id <> COALESCE(%(exclude)s, -1)
        ORDER BY s.shared DESC, jaccard DESC, f.owners_mid DESC NULLS LAST  -- game ít tag không được ưu tiên nhờ Jaccard
        LIMIT %(n)s
    """, {"tags": _norm(tags), "exclude": exclude, "n": min(limit, MAX_ROWS)})
    return _json({"target": target, "other_name_matches": others, "target_tags": tags, "similar": rows})


def market_segments(game_name: str | None = None) -> str:
    """Các phân khúc thị trường từ phân cụm K-Means (theo owners, CCU, giá, tỷ lệ khen): tên, số game và giá trị trung vị
    của từng phân khúc. Truyền game_name để biết game đó thuộc phân khúc nào và số liệu riêng của nó.

    Args:
        game_name: Tên game (tìm gần đúng), ví dụ "Stardew Valley".
    """
    args = {"game_name": game_name}
    _require_mining("mining.game_clusters")
    result = {"segments": _query("market_segments", args, """
        SELECT c.cluster_id, c.cluster_label, COUNT(*) AS n_games, COUNT(*) FILTER (WHERE f.is_free) AS n_free_games,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.owners_mid) AS median_owners,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.avg_ccu) AS median_ccu,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.price_vnd) AS median_price_vnd,
               ROUND(AVG(f.positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
               (ARRAY_AGG(f.game_title ORDER BY c.distance_to_center))[1:5] AS examples  -- game gần tâm cụm nhất
        FROM mining.game_clusters AS c JOIN marts.mart_mining_features AS f ON f.game_id = c.game_id
        GROUP BY c.cluster_id, c.cluster_label ORDER BY c.cluster_id
    """)}
    if game_name:
        game, others = _find_game("market_segments", game_name)
        result["game"] = _query("market_segments", args, """
            SELECT f.game_title, c.cluster_id, c.cluster_label, f.owners_min, f.owners_max, f.avg_ccu, f.is_free,
                   f.price_vnd, f.positive_ratio, f.total_reviews, f.release_date, f.is_in_universe
            FROM marts.mart_mining_features AS f LEFT JOIN mining.game_clusters AS c ON c.game_id = f.game_id
            WHERE f.game_id = %(id)s
        """, {"id": game["game_id"]})[0]
        result["other_name_matches"] = others
    return _json(result)


def top_charts(chart: str = "top_sellers", tag: str | None = None, genre: str | None = None, limit: int = 10) -> str:
    """Bảng xếp hạng chính thức mới nhất của Steam, dùng cho câu hỏi "game nào đang hot / bán chạy / đông người chơi
    nhất hiện nay". chart="top_sellers": top 50 bán chạy nhất tại Steam Việt Nam (chụp mỗi ngày, gồm cả game đang cho
    đặt trước: is_upcoming, rank_change so với hôm trước, most_played_rank = hạng trong top nhiều người chơi).
    chart="most_played": top 50 nhiều người chơi nhất toàn cầu của ngày gần nhất đã đủ dữ liệu, kèm CCU đỉnh và trung bình.
    Lọc tag/thể loại chỉ giữ các game TRONG top 50 có tag/thể loại đó; game mới ra có thể chưa có dữ liệu tag.

    Args:
        chart: "top_sellers" (bán chạy) hoặc "most_played" (nhiều người chơi).
        tag: Tag Steam tiếng Anh để lọc, ví dụ "FPS", "Survival", "Co-op".
        genre: Thể loại tiếng Anh để lọc, ví dụ "Action", "RPG".
        limit: Số game trả về (tối đa 50).
    """
    args = {"chart": chart, "tag": tag, "genre": genre, "limit": limit}
    if chart not in ("top_sellers", "most_played"):
        raise ValueError('chart phải là "top_sellers" hoặc "most_played".')
    filters = f"""
        (CAST(%(tag)s AS TEXT) IS NULL OR EXISTS (
          SELECT 1 FROM dw.bridge_game_tag AS b JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
          WHERE b.game_id = c.game_id AND {_norm_sql("t.tag_name")} = %(tag)s))
        AND (CAST(%(genre)s AS TEXT) IS NULL OR {_norm_sql("COALESCE(c.genres, '')")} LIKE '%%' || %(genre)s || '%%')
    """
    if chart == "top_sellers":
        sql = f"""
            SELECT c.catalog_date AS chart_date, c.rank, c.rank_yesterday, c.rank_change, c.game_title, c.genres,
                   c.is_free, c.price_vnd, c.price_initial_vnd, c.discount_pct, c.release_date, c.is_upcoming,
                   c.most_played_rank, COUNT(*) OVER () AS n_matching
            FROM marts.mart_top_sellers AS c WHERE {filters} ORDER BY c.rank LIMIT %(n)s"""
    else:
        sql = f"""
            SELECT c.full_date AS chart_date, c.ranking_order AS rank, c.game_title, c.genres, c.is_free, c.price_vnd,
                   c.discount_pct, c.peak_ccu, c.avg_ccu, COUNT(*) OVER () AS n_matching
            FROM marts.mart_executive_overview AS c WHERE {filters} ORDER BY c.ranking_order LIMIT %(n)s"""
    rows = _query("top_charts", args, sql, {"tag": _norm([tag])[0] if tag else None,
                                            "genre": _norm([genre])[0] if genre else None, "n": min(limit, MAX_ROWS)})
    return _json({"chart": chart, "chart_date": rows[0]["chart_date"] if rows else None,
                  "n_matching_in_top50": rows[0]["n_matching"] if rows else 0,
                  "games": [{k: v for k, v in r.items() if k not in ("chart_date", "n_matching")} for r in rows]})


_READONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def run_readonly_sql(query: str) -> str:
    """Dự phòng khi không công cụ nào khác trả lời được: chạy 1 câu SELECT (tối đa 50 dòng, quá 5 giây bị hủy). Không sửa
    được dữ liệu. CHỈ dùng đúng các bảng và cột dưới đây (không có bảng nào khác):
    - marts.mart_mining_features (1 dòng/game): game_id, game_title, app_type, is_free, price_vnd, num_languages,
      is_multiplayer, is_coop, release_date, developer_name, publisher_name, owners_min, owners_mid, owners_max,
      positive_reviews, negative_reviews, total_reviews, positive_ratio (0-1), is_high_positive, avg_ccu, peak_ccu,
      is_in_universe. LUÔN lọc WHERE is_in_universe AND app_type = 'game'; sắp xếp thêm NULLS LAST.
    - dw.bridge_game_tag (game_id, tag_key, vote_rank: 1 = tag được vote nhiều nhất) JOIN dw.dim_tag (tag_key, tag_name);
      dw.bridge_game_genre (game_id, genre_key) JOIN dw.dim_genre (genre_key, genre_name).
    - marts.mart_market_by_tag (tag_name, n_games, median_owners, avg_positive_ratio, pct_high_positive,
      median_price_vnd, pct_free, median_ccu); marts.mart_market_by_genre (genre_name, cùng các cột).
    - marts.mart_top_sellers (catalog_date, rank, game_id, game_title, genres, price_vnd, discount_pct, is_upcoming,
      most_played_rank); marts.mart_executive_overview (full_date, ranking_order, game_id, game_title, genres,
      peak_ccu, avg_ccu); marts.mart_daily_movers (game_title, status, peak_ccu_change_pct, discount_pct).
    - mining.tag_rules (antecedents TEXT[], consequents TEXT[], support, confidence, lift, is_high_positive);
      mining.game_clusters (game_id, cluster_id, cluster_label).
    Ví dụ top game theo tag: SELECT f.game_title, f.owners_mid, f.positive_ratio FROM marts.mart_mining_features f
    JOIN dw.bridge_game_tag b ON b.game_id = f.game_id JOIN dw.dim_tag t ON t.tag_key = b.tag_key
    WHERE t.tag_name = 'Survival' AND f.is_in_universe AND f.app_type = 'game' ORDER BY f.owners_mid DESC NULLS LAST

    Args:
        query: Đúng 1 câu SELECT (hoặc WITH ... SELECT) PostgreSQL, không có dấu chấm phẩy.
    """
    query = query.strip().rstrip(";")
    if not _READONLY_SQL.match(query) or ";" in query:
        raise ValueError("Chỉ được chạy đúng 1 câu SELECT; Copilot không được sửa dữ liệu.")
    # Bọc trong subquery để giới hạn số dòng; ghi/sửa đã bị chặn bởi role copilot_ro và phiên readonly
    return _json(_query("run_readonly_sql", {"query": query}, f"SELECT * FROM (\n{query}\n) AS q LIMIT {MAX_ROWS}"))


TOOLS = [market_overview, top_charts, tag_opportunities, price_benchmark, similar_games, market_segments, run_readonly_sql]
