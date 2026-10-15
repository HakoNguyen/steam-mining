import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import (
    get_db_connection,
    ensure_dim_date,
    ensure_dim_time
)

def process_ccu_snapshots(conn):
    cursor = conn.cursor()
    # Đọc từ raw.steam_ccu_json (appid, fetched_at đã được parse sẵn khi nạp raw)
    cursor.execute("SELECT appid, fetched_at, payload FROM raw.steam_ccu_json ORDER BY fetched_at;")
    raw_rows = cursor.fetchall()
    print("[Fact Loader] Processing CCU Snapshots...")

    processed_count = 0
    for game_id, snapshot_dt, payload in raw_rows:
        if not payload or not isinstance(payload, dict):
            continue

        response_data = payload.get("response", {})
        player_count = response_data.get("player_count")
        if player_count is None:
            continue

        # Placeholder lấy tên từ Daily Catalog, chỉ dùng "AppID xxx" khi game không có trong catalog
        cursor.execute(
            """
            INSERT INTO dim_game (game_id, game_title)
            VALUES (%s, COALESCE(
                (SELECT game_title FROM raw.game_catalog_daily
                 WHERE game_id = %s AND game_title IS NOT NULL
                 ORDER BY catalog_date DESC LIMIT 1),
                %s
            ))
            ON CONFLICT DO NOTHING;
            """,
            (game_id, game_id, f"AppID {game_id}")
        )

        date_key = ensure_dim_date(cursor, snapshot_dt)
        time_key = ensure_dim_time(cursor, snapshot_dt)

        cursor.execute("SELECT price_vnd FROM dim_game WHERE game_id = %s;", (game_id,))
        price_row = cursor.fetchone()
        price_vnd = price_row[0] if price_row and price_row[0] is not None else 0.00

        query = """
        INSERT INTO fact_player_snapshot (
                game_id, date_key, time_key, snapshot_timestamp,
                concurrent_players, price_vnd, discount_percent
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            ON CONFLICT (game_id, date_key, time_key) DO UPDATE SET
                concurrent_players = EXCLUDED.concurrent_players,
                snapshot_timestamp = EXCLUDED.snapshot_timestamp,
                updated_at = CURRENT_TIMESTAMP;
        """
        cursor.execute(query, (game_id, date_key, time_key, snapshot_dt, player_count, price_vnd))
        processed_count += 1
    conn.commit()
    cursor.close()
    print(f"[Fact Loader] Processed {processed_count} CCU snapshots.")

def aggregate_daily_game_performance(conn):
    cursor = conn.cursor()
    print("[Fact Loader] Aggregating Daily Game Performance...")
    query = """
        INSERT INTO fact_daily_game_performance (
            date_key, game_id, peak_ccu, avg_ccu, min_ccu,
            snapshot_count, price_vnd, discount_pct
        )
        SELECT
            date_key,
            game_id,
            MAX(concurrent_players) AS peak_ccu,
            ROUND(AVG(concurrent_players), 2) AS avg_ccu,
            MIN(concurrent_players) AS min_ccu,
            COUNT(*)::SMALLINT AS snapshot_count,
            AVG(price_vnd) AS price_vnd,
            COALESCE(AVG(discount_percent), 0)::SMALLINT AS discount_pct
        FROM fact_player_snapshot
        GROUP BY date_key, game_id
        ON CONFLICT (date_key, game_id) DO UPDATE SET
            peak_ccu = EXCLUDED.peak_ccu,
            avg_ccu = EXCLUDED.avg_ccu,
            min_ccu = EXCLUDED.min_ccu,
            snapshot_count = EXCLUDED.snapshot_count,
            price_vnd = EXCLUDED.price_vnd,
            discount_pct = EXCLUDED.discount_pct,
            updated_at = CURRENT_TIMESTAMP;
    """
    cursor.execute(query)
    conn.commit()
    cursor.close()
    print("[Fact Loader] Daily Game Performance aggregated successfully!")
def run_fact_pipeline():
    """
    Main runner for fact loading pipeline.
    """
    conn = get_db_connection()
    try:
        process_ccu_snapshots(conn)
        aggregate_daily_game_performance(conn)
        print("[Fact Pipeline] All fact tables populated successfully! 🎉")
    except Exception as e:
        conn.rollback()
        print(f"[Fact Pipeline Error] {e}")
        raise e
    finally:
        conn.close()
if __name__ == "__main__":
    run_fact_pipeline()
