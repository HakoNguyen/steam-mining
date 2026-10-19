"""
Công cụ tra cứu của Copilot (chức năng 3: trợ lý khảo sát thị trường). Mỗi công cụ là 1 hàm Python thuần chạy SQL
cố định trên warehouse bằng user chỉ-đọc copilot_ro; llm.py đăng ký các hàm này làm tool cho AI.
Mỗi câu SQL đã chạy được ghi vào trace để giao diện hiện mục "Copilot đã tra cứu gì".

Cần chạy mining trước (mining/association_rules.py, mining/kmeans_clustering.py) để có mining.tag_rules, mining.game_clusters.
"""
import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2.extras import RealDictCursor

ENV = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
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


def _connect():
    # Host/port chỉ lấy từ biến môi trường (Docker đặt postgres-dwh:5432); .env ghi host theo mạng Docker nên chạy
    # trên máy thì mặc định localhost:5433. Quyền chỉ-đọc + timeout 5s do role copilot_ro đảm bảo ở phía DB.
    conn = psycopg2.connect(host=os.environ.get("POSTGRES_HOST", "localhost"), port=os.environ.get("POSTGRES_PORT", "5433"),
                            dbname=ENV.get("POSTGRES_DB", "steam_dwh"), user=ENV.get("COPILOT_DB_USER", "copilot_ro"),
                            password=ENV.get("COPILOT_DB_PASSWORD"), cursor_factory=RealDictCursor)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def _query(tool, args, sql, params=None):
    entry = {"tool": tool, "args": args, "sql": sql.strip()}
    if (trace := _trace.get()) is not None:
        trace.append(entry)
    conn = _connect()
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
    table, key, value = ("marts.mart_market_by_genre", "genre_name", genre) if genre else ("marts.mart_market_by_tag", "tag_name", tag)
    if value:
        # khớp đúng (nếu có) đứng đầu, kèm các tên chứa từ khóa (biến thể như Rogue-lite, Action Roguelike)
        v = _norm([value])[0]
        rows = _query("market_overview", args, f"""
            SELECT * FROM {table} WHERE {_norm_sql(key)} LIKE %(p)s
            ORDER BY {_norm_sql(key)} = %(v)s DESC, n_games DESC LIMIT %(n)s
        """, {"v": v, "p": f"%{v}%", "n": limit})
        exact = bool(rows) and _norm([rows[0][key]])[0] == v
        result = {"market": rows[0] if exact else None, "related": rows[1:] if exact else rows}
    else:
        result = {"top_by_n_games": _query("market_overview", args,
                                           f"SELECT * FROM {table} ORDER BY n_games DESC LIMIT %(n)s", {"n": limit})}
    result["baseline_all_games"] = _baseline("market_overview")
    return _json(result)


def tag_opportunities(tags: list[str] | None = None, max_games: int | None = None, limit: int = 10) -> str:
    """Combo tag "được khen nhiều mà ít đối thủ": luật kết hợp Apriori {tag...} -> HIGH_POSITIVE (>= 90% review khen).
    confidence = tỷ lệ game có combo này được khen cao; lift = gấp bao nhiêu lần tỷ lệ chung; n_games = số game có combo (đối thủ).

    Args:
        tags: Chỉ lấy combo có chứa TẤT CẢ các tag này (tiếng Anh), ví dụ ["Roguelike"]. Bỏ trống để xem mọi combo.
        max_games: Chỉ lấy combo có tối đa ngần này game (ít đối thủ). Luật chỉ gồm combo có ít nhất ~3% số game.
        limit: Số combo trả về.
    """
    args = {"tags": tags, "max_games": max_games, "limit": limit}
    rows = _query("tag_opportunities", args, f"""
        SELECT antecedents AS tags, n_games, ROUND(confidence::NUMERIC, 3) AS confidence, ROUND(lift::NUMERIC, 2) AS lift
        FROM mining.tag_rules
        WHERE is_high_positive
          AND (CAST(%(tags)s AS TEXT[]) IS NULL
               OR (SELECT ARRAY_AGG({_norm_sql("a")}) FROM UNNEST(antecedents) AS a) @> CAST(%(tags)s AS TEXT[]))
          AND (%(max_games)s IS NULL OR n_games <= %(max_games)s)
        ORDER BY lift DESC, n_games
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
        SELECT f.* FROM marts.mart_mining_features AS f
        WHERE {UNIVERSE}
          AND (CAST(%(tags)s AS TEXT[]) IS NULL OR (
            SELECT COUNT(DISTINCT {_norm_sql("t.tag_name")})
            FROM dw.bridge_game_tag AS b JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
            WHERE b.game_id = f.game_id AND b.vote_rank <= 10 AND {_norm_sql("t.tag_name")} = ANY(CAST(%(tags)s AS TEXT[]))
          ) = CARDINALITY(CAST(%(tags)s AS TEXT[])))
          AND (CAST(%(genre)s AS TEXT) IS NULL OR EXISTS (
            SELECT 1 FROM dw.bridge_game_genre AS b JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
            WHERE b.game_id = f.game_id AND {_norm_sql("g.genre_name")} = %(genre)s))
    """
    params = {"tags": _norm(tags) if tags else None, "genre": _norm([genre])[0] if genre else None}
    summary = _query("price_benchmark", args, f"""
        WITH s AS ({scope})
        SELECT COUNT(*) AS n_games, ROUND(100.0 * AVG(is_free::INT), 1) AS pct_free,
               COUNT(*) FILTER (WHERE NOT is_free AND price_vnd > 0) AS n_paid_with_vn_price,
               PERCENTILE_CONT(ARRAY[0.25, 0.5, 0.75]) WITHIN GROUP (ORDER BY price_vnd)
                 FILTER (WHERE NOT is_free AND price_vnd > 0) AS price_p25_p50_p75
        FROM s
    """, params)[0]
    bands = _query("price_benchmark", args, f"""
        WITH s AS ({scope})
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
               f.release_date, c.cluster_label
        FROM score AS s
        JOIN marts.mart_mining_features AS f ON f.game_id = s.game_id
        LEFT JOIN mining.game_clusters AS c ON c.game_id = s.game_id
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
    result = {"segments": _query("market_segments", args, """
        SELECT c.cluster_id, c.cluster_label, COUNT(*) AS n_games, COUNT(*) FILTER (WHERE f.is_free) AS n_free_games,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.owners_mid) AS median_owners,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.avg_ccu) AS median_ccu,
               PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.price_vnd) AS median_price_vnd,
               ROUND(AVG(f.positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
               (ARRAY_AGG(f.game_title ORDER BY f.owners_mid DESC NULLS LAST))[1:5] AS examples
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


_READONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def run_readonly_sql(query: str) -> str:
    """Dự phòng khi không công cụ nào khác trả lời được: chạy 1 câu SELECT trên các schema marts, mining, dw
    (tối đa 50 dòng, quá 5 giây bị hủy). Không sửa được dữ liệu.

    Args:
        query: Đúng 1 câu SELECT (hoặc WITH ... SELECT) PostgreSQL, không có dấu chấm phẩy.
    """
    query = query.strip().rstrip(";")
    if not _READONLY_SQL.match(query) or ";" in query:
        raise ValueError("Chỉ được chạy đúng 1 câu SELECT; Copilot không được sửa dữ liệu.")
    # Bọc trong subquery để giới hạn số dòng; ghi/sửa đã bị chặn bởi role copilot_ro và phiên readonly
    return _json(_query("run_readonly_sql", {"query": query}, f"SELECT * FROM (\n{query}\n) AS q LIMIT {MAX_ROWS}"))


TOOLS = [market_overview, tag_opportunities, price_benchmark, similar_games, market_segments, run_readonly_sql]
