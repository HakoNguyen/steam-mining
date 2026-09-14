import os
import json
import time
from datetime import datetime
from io import BytesIO
from dotenv import dotenv_values
from minio import Minio

# 1. Load Environment Variables safely via dotenv_values
config = dotenv_values(".env")

MINIO_ENDPOINT = config.get("MINIO_ENDPOINT", "localhost:9000")
if not MINIO_ENDPOINT or "minio-datalake" in MINIO_ENDPOINT:
    MINIO_ENDPOINT = "localhost:9000"

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