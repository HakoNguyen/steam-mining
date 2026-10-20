import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import fetch_steam_api
from transformation.db_connect import get_db_connection

# Daily Seed List: mỗi ngày chụp 2 bảng xếp hạng chính thức của Steam, mọi DAG trong ngày đọc chung.
#   most_played: top game theo số người đang chơi (toàn cầu)
#   top_sellers: top game bán chạy trên Steam Việt Nam (gồm cả game đang cho đặt trước)
# Trước 20/10/2026 dùng SteamSpy top100in2weeks: các dòng đó vẫn giữ nguyên (source = 'steamspy_top100in2weeks').
MOST_PLAYED_URL = "https://api.steampowered.com/ISteamChartsService/GetGamesByConcurrentPlayers/v1/"
TOP_SELLERS_URL = "https://store.steampowered.com/search/results/?" + urlencode({
    "filter": "topsellers", "category1": 998,  # 998 = chỉ game (bỏ phần cứng, DLC, phần mềm)
    "cc": "VN", "l": "english", "json": 1, "count": 100, "start": 0,
})
SOURCES = {"most_played": "steam_charts", "top_sellers": "steam_store_topsellers"}
LEGACY_SOURCE = "steamspy_top100in2weeks"
FALLBACK_APPIDS = [1091500, 730, 570, 1086940, 271590]
CATALOG_LOCK_KEY = 50001  # pg_advisory_xact_lock key, chống 2 DAG sync cùng lúc

# Mỗi (ngày, bảng xếp hạng) chỉ dùng 1 nguồn: nguồn chính thức > SteamSpy cũ > chép lại hôm trước > danh sách cố định.
# staging.stg_game_catalog dùng cùng thứ tự này.
SOURCE_PREFERENCE = f"""
    CASE source WHEN '{SOURCES["most_played"]}' THEN 0 WHEN '{SOURCES["top_sellers"]}' THEN 0
                WHEN '{LEGACY_SOURCE}' THEN 1 WHEN 'carry_over' THEN 2 ELSE 3 END
"""

CATALOG_DDL = f"""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.game_catalog_daily (
    catalog_date DATE NOT NULL,
    chart VARCHAR(20) NOT NULL DEFAULT 'most_played',
    ranking_order INT NOT NULL,
    game_id INT NOT NULL,
    game_title VARCHAR(255),
    ccu_2weeks INT,
    concurrent_players INT,
    peak_ccu_today INT,
    source VARCHAR(50) NOT NULL DEFAULT '{LEGACY_SOURCE}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (catalog_date, chart, source, game_id)
);
-- Nâng cấp bảng tạo theo cấu trúc cũ (khóa chính catalog_date, game_id): chỉ thêm cột và đổi khóa, không xóa dòng nào.
-- Kiểm tra trước khi ALTER để các lần gọi sau không phải khóa bảng.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema = 'raw' AND table_name = 'game_catalog_daily' AND column_name = 'chart') THEN
    ALTER TABLE raw.game_catalog_daily
      ADD COLUMN chart VARCHAR(20) NOT NULL DEFAULT 'most_played',
      ADD COLUMN concurrent_players INT,
      ADD COLUMN peak_ccu_today INT;
    UPDATE raw.game_catalog_daily SET source = '{LEGACY_SOURCE}' WHERE source IS NULL;
    ALTER TABLE raw.game_catalog_daily ALTER COLUMN source SET NOT NULL;
    ALTER TABLE raw.game_catalog_daily DROP CONSTRAINT game_catalog_daily_pkey;
    ALTER TABLE raw.game_catalog_daily ADD PRIMARY KEY (catalog_date, chart, source, game_id);
  END IF;
END $$;
"""


def ensure_catalog_table(cursor):
    cursor.execute(CATALOG_DDL)


def fetch_most_played(limit=50):
    data = fetch_steam_api(MOST_PLAYED_URL)
    ranks = ((data or {}).get("response") or {}).get("ranks") or []
    return [{
        "game_id": int(r["appid"]),
        "game_title": None,  # API không trả tên; tên lấy từ dim_game
        "concurrent_players": r.get("concurrent_in_game"),
        "peak_ccu_today": r.get("peak_in_game"),
    } for r in ranks[:limit] if r.get("appid")]


def fetch_top_sellers(limit=50):
    data = fetch_steam_api(TOP_SELLERS_URL)
    games, seen = [], set()
    for item in (data or {}).get("items") or []:
        # appid nằm trong URL ảnh; bỏ qua gói (subs/bundles) vì không phải một game
        m = re.search(r"/apps/(\d+)/", item.get("logo") or "")
        if not m or int(m.group(1)) in seen:
            continue
        seen.add(int(m.group(1)))
        games.append({"game_id": int(m.group(1)), "game_title": (item.get("name") or "")[:255] or None,
                      "concurrent_players": None, "peak_ccu_today": None})
    return games[:limit]


FETCHERS = {"most_played": fetch_most_played, "top_sellers": fetch_top_sellers}


def _sync_chart(cursor, catalog_date, chart, limit, force):
    """Chụp 1 bảng xếp hạng cho 1 ngày. Không bao giờ xóa dòng SteamSpy cũ."""
    cursor.execute(
        "SELECT COUNT(*) FROM raw.game_catalog_daily WHERE catalog_date = %s AND chart = %s AND source <> %s;",
        (catalog_date, chart, LEGACY_SOURCE))
    if cursor.fetchone()[0] > 0 and not force:
        return "skipped"
    cursor.execute("DELETE FROM raw.game_catalog_daily WHERE catalog_date = %s AND chart = %s AND source <> %s;",
                   (catalog_date, chart, LEGACY_SOURCE))

    games = FETCHERS[chart](limit)
    if games:
        for rank, g in enumerate(games, start=1):
            cursor.execute(
                """
                INSERT INTO raw.game_catalog_daily
                    (catalog_date, chart, ranking_order, game_id, game_title, concurrent_players, peak_ccu_today, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (catalog_date, chart, rank, g["game_id"], g["game_title"], g["concurrent_players"],
                 g["peak_ccu_today"], SOURCES[chart]))
        return SOURCES[chart]

    # API lỗi: chép lại bảng xếp hạng của ngày gần nhất (đúng nguồn được ưu tiên của ngày đó)
    cursor.execute(
        f"""
        INSERT INTO raw.game_catalog_daily
            (catalog_date, chart, ranking_order, game_id, game_title, concurrent_players, peak_ccu_today, source)
        SELECT %s, chart, ranking_order, game_id, game_title, concurrent_players, peak_ccu_today, 'carry_over'
        FROM (
            SELECT *, RANK() OVER (ORDER BY {SOURCE_PREFERENCE}) AS source_rank
            FROM raw.game_catalog_daily
            WHERE chart = %s AND catalog_date = (
                SELECT MAX(catalog_date) FROM raw.game_catalog_daily WHERE chart = %s AND catalog_date < %s)
        ) AS prev
        WHERE source_rank = 1;
        """,
        (catalog_date, chart, chart, catalog_date))
    if cursor.rowcount > 0 or chart != "most_played":
        return "carry_over"
    for rank, game_id in enumerate(FALLBACK_APPIDS, start=1):
        cursor.execute(
            "INSERT INTO raw.game_catalog_daily (catalog_date, chart, ranking_order, game_id, source) "
            "VALUES (%s, %s, %s, %s, 'fallback');",
            (catalog_date, chart, rank, game_id))
    return "fallback"


def sync_daily_catalog(limit=50, force=False):
    catalog_date = datetime.utcnow().date()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ensure_catalog_table(cursor)
        cursor.execute("SELECT pg_advisory_xact_lock(%s);", (CATALOG_LOCK_KEY,))
        for chart in FETCHERS:
            source = _sync_chart(cursor, catalog_date, chart, limit, force)
            print(f"[Catalog] {catalog_date} {chart}: source={source}")
        conn.commit()
        cursor.close()
    except Exception as e:
        conn.rollback()
        print(f"[Catalog Error] {e}")
        raise e
    finally:
        conn.close()


def get_catalog_appids(catalog_date=None):
    """Game cần theo dõi trong ngày: hợp của 2 bảng xếp hạng (bỏ trùng), xếp theo thứ hạng tốt nhất."""
    catalog_date = catalog_date or datetime.utcnow().date()

    def _select():
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            ensure_catalog_table(cursor)
            cursor.execute(
                f"""
                SELECT game_id
                FROM (
                    SELECT game_id, ranking_order,
                           RANK() OVER (PARTITION BY chart ORDER BY {SOURCE_PREFERENCE}) AS source_rank
                    FROM raw.game_catalog_daily
                    WHERE catalog_date = %s
                ) AS c
                WHERE source_rank = 1
                GROUP BY game_id
                ORDER BY MIN(ranking_order), game_id;
                """,
                (catalog_date,)
            )
            rows = [row[0] for row in cursor.fetchall()]
            conn.commit()
            cursor.close()
            return rows
        finally:
            conn.close()

    appids = _select()
    if not appids:
        # DAG catalog chưa chạy trong ngày: sync ngay rồi đọc lại
        sync_daily_catalog()
        appids = _select()
    return appids


if __name__ == "__main__":
    sync_daily_catalog(force="--force" in sys.argv)
    print(get_catalog_appids())
