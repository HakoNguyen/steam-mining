import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import get_minio_client, MINIO_BUCKET_NAME, get_db_connection

def diagnose():
    client = get_minio_client()
    print("=== MinIO S3 Object Count by Prefix ===")
    for prefix in ["ccu/", "store/", "steamspy/", "reviews/"]:
        objs = list(client.list_objects(MINIO_BUCKET_NAME, prefix=prefix, recursive=True))
        print(f"Prefix '{prefix}': {len(objs)} files")

    print("\n=== Postgres DWH Row Counts ===")
    conn = get_db_connection()
    cur = conn.cursor()
    tables = [
        "dim_game", "dim_genre", "bridge_game_genre",
        "dim_tag", "bridge_game_tag", "dim_date", "dim_time",
        "fact_player_snapshot", "fact_daily_game_performance"
    ]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        count = cur.fetchone()[0]
        print(f"Table '{t}': {count} rows")
    cur.close()
    conn.close()

if __name__ == "__main__":
    diagnose()
