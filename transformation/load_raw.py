import sys
import re
import json
from pathlib import Path
from datetime import datetime, date, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from psycopg2.extras import execute_values
from transformation.db_connect import (
    get_db_connection,
    get_minio_client,
    get_minio_json,
    MINIO_BUCKET_NAME
)

# MinIO prefix -> bảng raw (mỗi file JSON = 1 dòng, giữ nguyên payload)
RAW_TABLES = {
    "store": "raw.steam_store_json",
    "steamspy": "raw.steam_steamspy_json",
    "ccu": "raw.steam_ccu_json",
    "reviews": "raw.steam_reviews_json",
    # 1 file = 1 batch 50 game của IStoreBrowseService; appid là game đầu batch
    "storebrowse": "raw.steam_storebrowse_json",
}

PARTITION_PATTERN = re.compile(r"year=(\d{4})/month=(\d{2})/day=(\d{2})/$")
FILE_PATTERN = re.compile(r"/[a-z]+_(\d+)_(\d{8}_\d{6})\.json$")

RAW_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    object_key VARCHAR(255) PRIMARY KEY,
    appid INT NOT NULL,
    partition_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS {index}_partition_idx ON {table} (partition_date);
CREATE INDEX IF NOT EXISTS {index}_appid_idx ON {table} (appid, fetched_at);
"""

WATERMARK_DDL = """
CREATE TABLE IF NOT EXISTS raw.load_watermark (
    source VARCHAR(50) PRIMARY KEY,
    last_partition_date DATE NOT NULL,
    files_loaded INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_raw_tables(cursor):
    cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    for table in RAW_TABLES.values():
        cursor.execute(RAW_TABLE_DDL.format(table=table, index=table.replace(".", "_")))
    cursor.execute(WATERMARK_DDL)


def list_partitions(client, source):
    """Duyệt prefix year=/month=/day= (không recursive) để lấy các ngày có dữ liệu."""
    partitions = []
    for year in client.list_objects(MINIO_BUCKET_NAME, prefix=f"{source}/"):
        for month in client.list_objects(MINIO_BUCKET_NAME, prefix=year.object_name):
            for day in client.list_objects(MINIO_BUCKET_NAME, prefix=month.object_name):
                match = PARTITION_PATTERN.search(day.object_name)
                if match:
                    y, m, d = (int(x) for x in match.groups())
                    partitions.append((date(y, m, d), day.object_name))
    return sorted(partitions)


def to_jsonb_text(payload):
    # Postgres JSONB không chấp nhận ký tự \u0000 (hay gặp trong review text)
    return json.dumps(payload, ensure_ascii=False).replace("\\u0000", "")


def load_source(conn, client, source, table):
    cursor = conn.cursor()
    cursor.execute("SELECT last_partition_date FROM raw.load_watermark WHERE source = %s;", (source,))
    row = cursor.fetchone()
    watermark = row[0] if row else None

    # Quét lại cả ngày watermark vì ngày đó có thể còn file mới sau lần nạp trước
    partitions = [(d, p) for d, p in list_partitions(client, source) if watermark is None or d >= watermark]
    print(f"[Raw Loader] {source}: watermark={watermark}, scanning {len(partitions)} partitions")

    total_loaded = 0
    total_failed = 0
    for partition_date, prefix in partitions:
        cursor.execute(f"SELECT object_key FROM {table} WHERE partition_date = %s;", (partition_date,))
        existing_keys = {r[0] for r in cursor.fetchall()}

        rows = []
        for obj in client.list_objects(MINIO_BUCKET_NAME, prefix=prefix, recursive=True):
            if obj.object_name in existing_keys:
                continue
            match = FILE_PATTERN.search(obj.object_name)
            if not match:
                continue
            payload = get_minio_json(client, obj.object_name)
            if payload is None:
                total_failed += 1
                continue

            fetched_at = datetime.strptime(match.group(2), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            rows.append((obj.object_name, int(match.group(1)), partition_date, fetched_at, to_jsonb_text(payload)))

        if rows:
            execute_values(
                cursor,
                f"""
                INSERT INTO {table} (object_key, appid, partition_date, fetched_at, payload)
                VALUES %s
                ON CONFLICT (object_key) DO NOTHING;
                """,
                rows,
                template="(%s, %s, %s, %s, %s::jsonb)"
            )

        # Watermark tiến theo từng partition, cùng transaction với dữ liệu
        cursor.execute(
            """
            INSERT INTO raw.load_watermark (source, last_partition_date, files_loaded)
            VALUES (%s, %s, %s)
            ON CONFLICT (source) DO UPDATE SET
                last_partition_date = EXCLUDED.last_partition_date,
                files_loaded = EXCLUDED.files_loaded,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (source, partition_date, len(rows))
        )
        conn.commit()
        total_loaded += len(rows)

    cursor.close()
    print(f"[Raw Loader] {source}: loaded {total_loaded} new files into {table} (failed: {total_failed})")
    return total_loaded


def run_raw_load():
    conn = get_db_connection()
    client = get_minio_client()
    try:
        cursor = conn.cursor()
        ensure_raw_tables(cursor)
        conn.commit()
        cursor.close()

        for source, table in RAW_TABLES.items():
            load_source(conn, client, source, table)
        print("[Raw Loader] MinIO ➔ raw schema completed!")
    except Exception as e:
        conn.rollback()
        print(f"[Raw Loader Error] {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    run_raw_load()
