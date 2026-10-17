import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import fetch_steam_api
from transformation.db_connect import get_db_connection

# Daily Seed List: 1 snapshot Top 50 game / ngày, mọi DAG trong ngày đọc chung
TOP_GAMES_URL = "https://steamspy.com/api.php?request=top100in2weeks"
FALLBACK_APPIDS = [1091500, 730, 570, 1086940, 271590]
CATALOG_LOCK_KEY = 50001  # pg_advisory_xact_lock key, chống 2 DAG sync cùng lúc

CATALOG_DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.game_catalog_daily (
    catalog_date DATE NOT NULL,
    ranking_order INT NOT NULL,
    game_id INT NOT NULL,
    game_title VARCHAR(255),
    ccu_2weeks INT,
    source VARCHAR(50) DEFAULT 'steamspy_top100in2weeks',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (catalog_date, game_id)
);
"""


def ensure_catalog_table(cursor):
    cursor.execute(CATALOG_DDL)


def fetch_top_games(limit=50):
    data = fetch_steam_api(TOP_GAMES_URL)
    if not data or not isinstance(data, dict):
        return []

    games = []
    for key, info in data.items():
        if not key.isdigit() or not isinstance(info, dict):
            continue
        games.append({
            "game_id": int(key),
            "game_title": (info.get("name") or "")[:255] or None,
            "ccu_2weeks": int(info.get("ccu") or 0),
        })
    # Không dựa vào thứ tự key của dict, sắp xếp tường minh theo CCU
    games.sort(key=lambda g: g["ccu_2weeks"], reverse=True)
    return games[:limit]


def sync_daily_catalog(limit=50, force=False):
    catalog_date = datetime.utcnow().date()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ensure_catalog_table(cursor)
        cursor.execute("SELECT pg_advisory_xact_lock(%s);", (CATALOG_LOCK_KEY,))

        cursor.execute(
            "SELECT COUNT(*) FROM raw.game_catalog_daily WHERE catalog_date = %s;",
            (catalog_date,)
        )
        if cursor.fetchone()[0] > 0 and not force:
            conn.commit()
            print(f"[Catalog] Snapshot {catalog_date} already exists, skipping.")
            return

        cursor.execute("DELETE FROM raw.game_catalog_daily WHERE catalog_date = %s;", (catalog_date,))

        games = fetch_top_games(limit)
        if games:
            for rank, game in enumerate(games, start=1):
                cursor.execute(
                    """
                    INSERT INTO raw.game_catalog_daily
                        (catalog_date, ranking_order, game_id, game_title, ccu_2weeks, source)
                    VALUES (%s, %s, %s, %s, %s, 'steamspy_top100in2weeks');
                    """,
                    (catalog_date, rank, game["game_id"], game["game_title"], game["ccu_2weeks"])
                )
            source = "steamspy_top100in2weeks"
        else:
            # API lỗi: giữ nguyên danh sách của ngày gần nhất
            cursor.execute(
                """
                INSERT INTO raw.game_catalog_daily
                    (catalog_date, ranking_order, game_id, game_title, ccu_2weeks, source)
                SELECT %s, ranking_order, game_id, game_title, ccu_2weeks, 'carry_over'
                FROM raw.game_catalog_daily
                WHERE catalog_date = (
                    SELECT MAX(catalog_date) FROM raw.game_catalog_daily WHERE catalog_date < %s
                );
                """,
                (catalog_date, catalog_date)
            )
            source = "carry_over"
            if cursor.rowcount == 0:
                for rank, game_id in enumerate(FALLBACK_APPIDS, start=1):
                    cursor.execute(
                        """
                        INSERT INTO raw.game_catalog_daily (catalog_date, ranking_order, game_id, source)
                        VALUES (%s, %s, %s, 'fallback');
                        """,
                        (catalog_date, rank, game_id)
                    )
                source = "fallback"

        conn.commit()
        cursor.execute(
            "SELECT COUNT(*) FROM raw.game_catalog_daily WHERE catalog_date = %s;",
            (catalog_date,)
        )
        print(f"[Catalog] Snapshot {catalog_date}: {cursor.fetchone()[0]} games (source={source}).")
        cursor.close()
    except Exception as e:
        conn.rollback()
        print(f"[Catalog Error] {e}")
        raise e
    finally:
        conn.close()


def get_catalog_appids(catalog_date=None):
    catalog_date = catalog_date or datetime.utcnow().date()

    def _select():
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            ensure_catalog_table(cursor)
            cursor.execute(
                """
                SELECT game_id FROM raw.game_catalog_daily
                WHERE catalog_date = %s ORDER BY ranking_order ASC;
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
    sync_daily_catalog()
    print(get_catalog_appids())
