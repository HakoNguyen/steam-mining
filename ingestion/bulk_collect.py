"""
Thu hàng loạt game cho mining: lấy appid từ SteamSpy request=all (xếp theo owners giảm dần,
1000 game/trang), mỗi game gọi CCU + SteamSpy appdetails, metadata Store lấy theo batch qua
IStoreBrowseService (store.steampowered.com bị chặn ở mạng VN nên bỏ appdetails/reviews).
Chạy lại an toàn: bỏ qua appid đã có file steamspy/ trong MinIO.

    python ingestion/bulk_collect.py [so_trang]
    python ingestion/bulk_collect.py reviews   # cần truy cập được store.steampowered.com (VPN)
"""
import re
import sys
import time

from collector import (
    MINIO_BUCKET_NAME,
    collect_ccu,
    collect_reviews,
    collect_steamspy,
    collect_store_browse,
    fetch_steam_api,
    get_minio_client,
)


def collected_appids(client, prefix="steamspy/"):
    objects = client.list_objects(MINIO_BUCKET_NAME, prefix=prefix, recursive=True)
    return {int(m.group(1)) for o in objects if (m := re.search(r"_(\d+)_\d{8}_\d{6}\.json$", o.object_name))}


def main(pages=1):
    client = get_minio_client()
    done = collected_appids(client)

    appids = []
    for page in range(pages):
        if page:
            time.sleep(60)  # SteamSpy request=all: 1 lần/phút
        data = fetch_steam_api(f"https://steamspy.com/api.php?request=all&page={page}") or {}
        appids += [int(k) for k in data if k.isdigit()]

    todo = [a for a in appids if a not in done]
    print(f"{len(appids)} appid, đã có {len(appids) - len(todo)}, cần thu {len(todo)}")

    collect_store_browse(todo, client)
    for i, appid in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {appid}", flush=True)
        collect_ccu(appid, client)
        collect_steamspy(appid, client)
        time.sleep(1)  # SteamSpy appdetails ~1 req/s


def main_reviews():
    """Reviews API cho mọi game đã có trong lake mà chưa có reviews/."""
    client = get_minio_client()
    todo = sorted(collected_appids(client) - collected_appids(client, "reviews/"))
    print(f"cần thu review {len(todo)} game")
    for i, appid in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {appid}", flush=True)
        collect_reviews(appid, client)
        time.sleep(1.5)  # Store ~200 req/5 phút


if __name__ == "__main__":
    if sys.argv[1:] == ["reviews"]:
        main_reviews()
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
