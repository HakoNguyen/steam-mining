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

def get_target_appids():
    # Mọi DAG đọc chung Daily Catalog (raw.game_catalog_daily) thay vì tự gọi SteamSpy
    from ingestion.catalog import get_catalog_appids
    return get_catalog_appids()

# 4. Fetch Steam API with curl_cffi
def fetch_steam_api(url, impersonate='chrome124', retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, impersonate=impersonate, timeout=15)
            if response.status_code == 200:
                return response.json()
            print(f"  [Retry {attempt+1}/{retries}] HTTP {response.status_code} from {url}")
        except Exception as e:
            print(f"  [Retry {attempt+1}/{retries}] Error fetching {url}: {e}")
        # Chờ tăng dần 2s, 4s (không chờ sau lần cuối), áp dụng cho cả lỗi mạng lẫn HTTP != 200
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    print(f"  [Gave up] {url}")
    return None

# 5. Collectors for 4 APIs (trả về True nếu đã lưu được file lên MinIO)
def collect_ccu(appid, client):
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "ccu", appid, data)
        return True
    return False

def collect_store_details(appid, client):
    # cc=vn: giá luôn trả về VND, không phụ thuộc vùng của máy gọi
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english&cc=vn"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "store", appid, data)
        return True
    return False

def collect_steamspy(appid, client):
    url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "steamspy", appid, data)
        return True
    return False

def collect_reviews(appid, client):
    url = f"https://store.steampowered.com/appreviews/{appid}?json=1&language=english&cursor=*&num_per_page=50"
    data = fetch_steam_api(url)
    if data:
        save_json_to_minio(client, "reviews", appid, data)
        return True
    return False

def collect_batch(appids, collectors, client, min_success_rate=0.8, retry_wait=30):
    """Chạy từng collector cho mọi appid, thử lại các game lỗi 1 lượt.
    Raise lỗi (task Airflow chuyển failed) nếu tỷ lệ thành công thấp hơn min_success_rate."""
    low_success = []
    for collect_fn in collectors:
        failed = [appid for appid in appids if not collect_fn(appid, client)]
        if failed:
            print(f"[Collector] {collect_fn.__name__}: {len(failed)} failed, retrying in {retry_wait}s...")
            time.sleep(retry_wait)
            failed = [appid for appid in failed if not collect_fn(appid, client)]

        ok = len(appids) - len(failed)
        print(f"[Collector] {collect_fn.__name__}: {ok}/{len(appids)} OK, failed: {failed}")
        if appids and ok / len(appids) < min_success_rate:
            low_success.append(f"{collect_fn.__name__} {ok}/{len(appids)}")

    if low_success:
        raise RuntimeError(
            f"[Collector] Success rate below {min_success_rate:.0%}: {', '.join(low_success)}. "
            "Check network access to Steam."
        )

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

