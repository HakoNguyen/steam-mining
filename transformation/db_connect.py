import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import dotenv_values
from minio import Minio
from datetime import datetime

config = dotenv_values('.env')

# PostgreSQL
DB_HOST = os.environ.get('POSTGRES_HOST') or config.get('POSTGRES_HOST') or 'localhost'
DB_PORT = os.environ.get("POSTGRES_PORT") or config.get("POSTGRES_PORT") or "5433"
DB_NAME = config.get("POSTGRES_DB", "steam_dwh")
DB_USER = config.get("POSTGRES_USER", "admin")
DB_PASS = config.get("POSTGRES_PASSWORD", "adminpassword123")

# MinIO
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or config.get("MINIO_ENDPOINT") or "localhost:9000"
MINIO_ROOT_USER = config.get("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = config.get("MINIO_ROOT_PASSWORD", "adminpassword123")
MINIO_BUCKET_NAME = config.get("MINIO_BUCKET_NAME", "raw-steam-data")


def get_db_connection():
    try: 
        conn = psycopg2.connect(
            host=DB_HOST, 
            port=DB_PORT,
            dbname=DB_NAME, 
            user=DB_USER,
            password=DB_PASS
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f'Error {e} occurred while connecting to database {DB_NAME}')
        raise e


def get_minio_client():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False
    )
    return client


def get_minio_json(client, object_name):
    try:
        response = client.get_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=object_name
        )
        data = json.loads(response.read().decode('utf-8'))
        response.close()
        return data
    except Exception as e:
        print(f"Error occurred while reading file {object_name} from MinIO: {e}")
        return None


def ensure_dim_date(cursor, date_obj):
    date_key = int(date_obj.strftime('%Y%m%d'))
    cursor.execute('SELECT 1 FROM dim_date WHERE date_key = %s', (date_key,))
    if cursor.fetchone():
        return date_key

    full_date = date_obj.date()
    day_of_week = date_obj.isoweekday()
    month = date_obj.month
    quarter = (month - 1) // 3 + 1
    year = date_obj.year
    is_weekend = day_of_week in (6, 7)

    query = """
    INSERT INTO dim_date (date_key, full_date, day_of_week, month, quarter, year, is_weekend)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (date_key) DO NOTHING;
    """
    cursor.execute(query, (date_key, full_date, day_of_week, month, quarter, year, is_weekend))
    return date_key


def ensure_dim_time(cursor, date_obj):
    hour = date_obj.hour
    minute = date_obj.minute
    time_key = hour * 100 + minute

    if 5 <= hour < 12: 
        day_part = 'Morning'
    elif 12 <= hour < 17:
        day_part = 'Afternoon'
    elif 17 <= hour < 22:
        day_part = 'Evening'
    else: 
        day_part = 'Night'
    
    query = """
    INSERT INTO dim_time (time_key, hour_utc, minute_utc, day_part)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (time_key) DO NOTHING;
    """
    cursor.execute(query, (time_key, hour, minute, day_part))
    return time_key

    