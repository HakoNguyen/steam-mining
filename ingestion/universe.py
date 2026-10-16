import re
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import fetch_steam_api
from transformation.db_connect import get_db_connection

# Game Universe: ~2.000 game nhiều owners nhất (SteamSpy request=all), làm lại mỗi tuần, phục vụ Data Mining.
# Khác catalog Top 50 (dashboard, CCU theo giờ): tập này rộng hơn, chỉ cần thu thập 1 lần/tuần.
ALL_GAMES_URL = "https://steamspy.com/api.php?request=all&page={page}"
UNIVERSE_LOCK_KEY = 50002  # pg_advisory_xact_lock key

UNIVERSE_DDL = """
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.game_universe (
    snapshot_date DATE NOT NULL,
    owners_rank INT NOT NULL,
    game_id INT NOT NULL,
    game_title VARCHAR(255),
    owners_range VARCHAR(50),
    source VARCHAR(50) DEFAULT 'steamspy_all',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, game_id)
);
"""


def ensure_universe_table(cursor):
    cursor.execute(UNIVERSE_DDL)


def owners_lower_bound(owners_range):
    nums = re.findall(r"\d[\d,]*", owners_range or "")
    return int(nums[0].replace(",", "")) if nums else 0


def fetch_universe(pages=2):
    """SteamSpy request=all: 1.000 game/trang, giới hạn 1 request/phút."""
    games = {}
    for page in range(pages):
        if page:
            time.sleep(60)
        data = fetch_steam_api(ALL_GAMES_URL.format(page=page))
        if not data or not isinstance(data, dict):
            print(f"[Universe] Page {page} failed")
            return []
        for key, info in data.items():
            if key.isdigit() and isinstance(info, dict):
                games[int(key)] = {
                    "game_id": int(key),
                    "game_title": (info.get("name") or "")[:255] or None,
                    "owners_range": (info.get("owners") or "")[:50] or None,
                    "ccu": int(info.get("ccu") or 0),
                }
    # Xếp hạng tường minh theo owners (cận dưới), hòa thì theo CCU
    ranked = sorted(games.values(), key=lambda g: (owners_lower_bound(g["owners_range"]), g["ccu"]), reverse=True)
    return ranked


def sync_game_universe(pages=2, force=False):
    snapshot_date = datetime.utcnow().date()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ensure_universe_table(cursor)
        cursor.execute("SELECT pg_advisory_xact_lock(%s);", (UNIVERSE_LOCK_KEY,))

        cursor.execute("SELECT COUNT(*) FROM raw.game_universe WHERE snapshot_date = %s;", (snapshot_date,))
        if cursor.fetchone()[0] > 0 and not force:
            conn.commit()
            print(f"[Universe] Snapshot {snapshot_date} already exists, skipping.")
            return

        cursor.execute("DELETE FROM raw.game_universe WHERE snapshot_date = %s;", (snapshot_date,))
        games = fetch_universe(pages)
        if games:
            for rank, game in enumerate(games, start=1):
                cursor.execute(
                    """
                    INSERT INTO raw.game_universe (snapshot_date, owners_rank, game_id, game_title, owners_range)
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (snapshot_date, rank, game["game_id"], game["game_title"], game["owners_range"])
                )
            source = "steamspy_all"
        else:
            # API lỗi: giữ nguyên tập game của lần gần nhất
            cursor.execute(
                """
                INSERT INTO raw.game_universe (snapshot_date, owners_rank, game_id, game_title, owners_range, source)
                SELECT %s, owners_rank, game_id, game_title, owners_range, 'carry_over'
                FROM raw.game_universe
                WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM raw.game_universe WHERE snapshot_date < %s);
                """,
                (snapshot_date, snapshot_date)
            )
            source = "carry_over"
            if cursor.rowcount == 0:
                raise RuntimeError("[Universe] SteamSpy request=all failed and no previous snapshot exists")

        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM raw.game_universe WHERE snapshot_date = %s;", (snapshot_date,))
        print(f"[Universe] Snapshot {snapshot_date}: {cursor.fetchone()[0]} games (source={source}).")
        cursor.close()
    except Exception as e:
        conn.rollback()
        print(f"[Universe Error] {e}")
        raise e
    finally:
        conn.close()


def get_universe_appids():
    """Tập game của snapshot gần nhất (không nhất thiết là hôm nay, vì chạy hàng tuần)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        ensure_universe_table(cursor)
        cursor.execute(
            """
            SELECT game_id FROM raw.game_universe
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM raw.game_universe)
            ORDER BY owners_rank;
            """
        )
        appids = [row[0] for row in cursor.fetchall()]
        conn.commit()
        cursor.close()
        return appids
    finally:
        conn.close()


if __name__ == "__main__":
    sync_game_universe()
    print(len(get_universe_appids()))
