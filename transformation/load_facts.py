import sys
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import (
    get_db_connection,
    get_minio_client,
    get_minio_json,
    ensure_dim_date,
    ensure_dim_time,
    MINIO_BUCKET_NAME
)

def process_ccu_snapshots(conn, client):
    cursor = conn.cursor()
    objects = client.list_objects(MINIO_BUCKET_NAME, pref="ccu/", recursive=True)
    print("[Fact Loader] Processing CCU Snapshots...")
    
    processed_count = 0
    for obj in objects:
        payload = get_minio_json(client, obj.object_name)
        if not payload or not isinstance(payload, dict):
            continue

        response_data = payload.get("response", {})
        player_count = response_data.get("player_count")
        if player_count is None:
            continue

        match = re.search(r"ccu_(\d+)_(\d{8}_\d{6})\.json", obj.object_name)
        if match:
            game_id = int(match.group(1))
            dt_str = match.group(2)
            try:
                snapshot_dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
            except ValueError:
                snapshot_dt = datetime.utcnow()
        else:
            continue

        cursor.execute(
            "INSERT INTO dim_game (game_id, game_title) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (game_id, f"AppID {game_id}")
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
                snapshot_timestamp = EXCLUDED.snapshot_timestamp;
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
            discount_pct = EXCLUDED.discount_pct;
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
    client = get_minio_client()
    try:
        process_ccu_snapshots(conn, client)
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
