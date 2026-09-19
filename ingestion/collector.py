import os
import json
import time
from datetime import datetime
from io import BytesIO
from dotenv import dotenv_values
from minio import Minio

# 1. Load Environment Variables safely
config = dotenv_values(".env")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT") or config.get("MINIO_ENDPOINT") or "localhost:9000"

MINIO_ROOT_USER = config.get("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = config.get("MINIO_ROOT_PASSWORD", "adminpassword123")
MINIO_BUCKET_NAME = config.get("MINIO_BUCKET_NAME", "raw-steam-data")

# 2. MinIO Helper
def get_minio_client():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False
    )
    existing_buckets = [b.name for b in client.list_buckets()]
    if MINIO_BUCKET_NAME not in existing_buckets:
        client.make_bucket(MINIO_BUCKET_NAME)
    return client

# Import curl_cffi for Steam APIs
from curl_cffi import requests

# 3. Save Payload to MinIO S3 Lake
def save_json_to_minio(client, source_name, appid, payload):
    now = datetime.utcnow()
    partition_path = f"{source_name}/year={now.strftime('%Y')}/month={now.strftime('%m')}/day={now.strftime('%d')}"
    filename = f"{source_name}_{appid}_{now.strftime('%Y%m%d_%H%M%S')}.json"
    object_name = f"{partition_path}/{filename}"

    json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    data_stream = BytesIO(json_bytes)

    client.put_object(
        bucket_name=MINIO_BUCKET_NAME,
        object_name=object_name,
        data=data_stream,
        length=len(json_bytes),
        content_type='application/json'
    )
    print(f"[MinIO S3 OK] Saved: s3://{MINIO_BUCKET_NAME}/{object_name}")
    return object_name

def get_target_appids(limit=50):
    url = "https://steamspy.com/api.php?request=top100in2weeks"
    data = fetch_steam_api(url)
    if data and isinstance(data, dict):
        appids = [int(k) for k in data.keys() if k.isdigit()]
        if appids:
            return appids[:limit]
    return [1091500, 730, 570, 1086940, 271590]

# 4. Fetch Steam API with curl_cffi
def fetch_steam_api(url, impersonate='chrome124', retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, impersonate=impersonate, timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"  [Retry {attempt+1}/{retries}] Error fetching {url}: {e}")
            time.sleep(2)
    return None

# 5. Collectors for 4 APIs
def collect_ccu(appid, client):
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "ccu", appid, data)

def collect_store_details(appid, client):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "store", appid, data)

def collect_steamspy(appid, client):
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "steamspy", appid, data)

def collect_reviews(appid, client):
    url = f"https://store.steampowered.com/appreviews/{appid}?json=1&language=english&cursor=*&num_per_page=50"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "reviews", appid, data)

# 6. Main Pipeline Collector Runner
def run_collector(appids=[1091500, 730, 570]):
    client = get_minio_client()
    print(f"Starting collection for {len(appids)} AppIDs...")

    for appid in appids:
        print(f"\nProcessing AppID: {appid}")
        collect_ccu(appid, client)
        time.sleep(0.5)
        collect_store_details(appid, client)
        time.sleep(0.5)
        collect_steamspy(appid, client)
        time.sleep(0.5)
        collect_reviews(appid, client)
        time.sleep(0.5)

if __name__ == "__main__":
    run_collector()

from networkx.algorithms.centrality import reaching
import urllib.request
import json
import sqlite3
import datetime
import time

DB_PATH = "raw_ccu.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_ccu (
            game_id INTEGER NOT NULL,
            snapshot_time TEXT NOT NULL, 
            player_count INTEGER NOT NULL, 
            PRIMARY KEY (game_id, snapshot_time)
        )
    """)
    conn.commit()
    conn.close()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'
}

def fetch_player_count(appid): 
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=5) as res: 
            data = json.loads(res.read().decode('utf-8'))
            return data.get('response', {}).get('player_count', 0)
    except Exception as e:
        print(f"error when fetching {appid}")
        return None 

def get_top_appids():
    url = "https://steamspy.com/api.php?request=top100in2weeks"
    try: 
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode('utf-8'))
            return [int(k) for k in data.keys() if k.isdigit()]
    except Exception as e: 
        print("Error getting top appids:")
        return [730, 570, 1086940, 271590, 1172470]

def run_collection_cycle():
    init_db()

    target_appids = get_top_appids()

    snapshot_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:00:00")
    print(f"[{snapshot_time}] Starting collection cycle for {len(target_appids)} games...")
    
    conn = sqlite3.connect(DB_PATH)
    cusor = conn.cursor()

    sucess = 0
    for appid in target_appids: 
        count = fetch_player_count(appid)
        if count is not None: 
            cusor.execute("""
            INSERT OR REPLACE INTO raw_ccu (game_id, snapshot_time, player_count)
            VALUES (?, ?, ?)
            """, (appid, snapshot_time, count))
            sucess +=1 
            time.sleep(0.2) # rate limit
    
    conn.commit()
    conn.close()
    print(f"[DONE] Inserted {sucess}/{len(target_appids)} records to {DB_PATH}")

if __name__ == "__main__":
    run_collection_cycle()
