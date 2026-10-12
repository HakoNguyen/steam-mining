import re
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import (
    get_db_connection,
    get_minio_client,
    get_minio_json,
    MINIO_BUCKET_NAME
)


def parse_release_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return None

    date_formats = [
        "%d %b, %Y",    # e.g., "21 Aug, 2012"
        "%b %d, %Y",    # e.g., "Aug 21, 2012"
        "%Y-%m-%d",     # e.g., "2012-08-21"
        "%d %B, %Y",    # e.g., "21 August, 2012"
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    return None


# Steam category ids (appdetails categories / storebrowse supported_player_categoryids)
MULTIPLAYER_CATEGORY_IDS = {1, 24, 36, 37, 47, 49}   # Multi-player, Shared/Split Screen, Online/LAN/Shared PvP
COOP_CATEGORY_IDS = {9, 38, 39, 48}                  # Co-op, Online/Shared/LAN Co-op
STORE_APP_TYPES = {0: "game", 1: "demo", 2: "mod", 4: "dlc", 6: "software"}


def parse_owners(owners_str):
    """SteamSpy "20,000,000 .. 50,000,000" -> (20000000, 50000000)."""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", owners_str or "")]
    return (nums[0], nums[1]) if len(nums) == 2 else (None, None)


def count_appdetails_languages(languages_html):
    """appdetails: "English<strong>*</strong>, French<br><strong>*</strong>languages with full audio support" -> 2."""
    text = re.sub(r"<[^>]+>", "", (languages_html or "").split("<br>")[0])
    return len([lang for lang in text.split(",") if lang.strip()])


def upsert_genre(cursor, game_id, genre_name):
    cursor.execute(
        "INSERT INTO dim_genre (genre_name) VALUES (%s) ON CONFLICT (genre_name) DO NOTHING;",
        (genre_name,)
    )
    cursor.execute(
        "SELECT genre_id FROM dim_genre WHERE genre_name = %s;",
        (genre_name,)
    )
    genre_row = cursor.fetchone()
    if genre_row:
        cursor.execute(
            "INSERT INTO bridge_game_genre (game_id, genre_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
            (game_id, genre_row[0])
        )


def upsert_dim_game(cursor, row):
    cursor.execute("""
        INSERT INTO dim_game (
            game_id, game_title, app_type, release_date_iso, is_free,
            price_vnd, publisher_name, developer_name,
            languages_count, has_multiplayer, has_coop
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(game_id) DO UPDATE SET
            game_title = EXCLUDED.game_title,
            app_type = EXCLUDED.app_type,
            release_date_iso = COALESCE(EXCLUDED.release_date_iso, dim_game.release_date_iso),
            is_free = EXCLUDED.is_free,
            price_vnd = EXCLUDED.price_vnd,
            publisher_name = EXCLUDED.publisher_name,
            developer_name = EXCLUDED.developer_name,
            languages_count = EXCLUDED.languages_count,
            has_multiplayer = EXCLUDED.has_multiplayer,
            has_coop = EXCLUDED.has_coop,
            updated_at = CURRENT_TIMESTAMP;
    """, row)


def process_store_dimensions(conn, client):
    cursor = conn.cursor()
    objects = client.list_objects(MINIO_BUCKET_NAME, prefix="store/", recursive=True)

    print("[Dimension Loader] Processing Store Details...")
    processed_count = 0

    for obj in objects:
        payload = get_minio_json(client, obj.object_name)
        if not payload or not isinstance(payload, dict):
            continue

        for appid_str, game_data in payload.items():
            if not game_data.get("success") or "data" not in game_data:
                continue

            data = game_data["data"]
            game_id = int(appid_str)
            game_title = data.get("name", "Unknown Game")[:255]
            app_type = data.get("type", "game")[:20]
            is_free = data.get("is_free", False)

            price_overview = data.get("price_overview", {})
            price_raw = price_overview.get("final", 0) if not is_free else 0
            price_vnd = float(price_raw) / 100.0

            release_date_str = data.get('release_date', {}).get("date", "")
            release_date_iso = parse_release_date(release_date_str)

            developers = ", ".join(data.get("developers", []))[:255]
            publishers = ", ".join(data.get("publishers", []))[:255]

            category_ids = {c.get("id") for c in data.get("categories", [])}

            upsert_dim_game(cursor, (
                game_id, game_title, app_type, release_date_iso,
                is_free, price_vnd, publishers, developers,
                count_appdetails_languages(data.get("supported_languages")),
                bool(category_ids & MULTIPLAYER_CATEGORY_IDS),
                bool(category_ids & COOP_CATEGORY_IDS)
            ))

            genres = data.get("genres", [])
            for g in genres:
                genre_name = g.get("description", "").strip()
                if genre_name:
                    upsert_genre(cursor, game_id, genre_name)

            processed_count += 1

    conn.commit()
    cursor.close()
    print(f"[Dimension Loader] Processed {processed_count} store games.")


def process_storebrowse_dimensions(conn, client):
    """IStoreBrowseService/GetItems (api.steampowered.com) - thay appdetails khi store.steampowered.com bị chặn."""
    cursor = conn.cursor()
    objects = client.list_objects(MINIO_BUCKET_NAME, prefix="storebrowse/", recursive=True)

    print("[Dimension Loader] Processing Store Browse Items...")
    processed_count = 0

    for obj in objects:
        payload = get_minio_json(client, obj.object_name)
        if not payload or not isinstance(payload, dict):
            continue

        for item in payload.get("response", {}).get("store_items", []):
            if item.get("success") != 1 or not item.get("appid"):
                continue

            is_free = bool(item.get("is_free"))
            price_cents = item.get("best_purchase_option", {}).get("final_price_in_cents")
            price_vnd = 0.0 if is_free or price_cents is None else int(price_cents) / 100.0

            release_ts = item.get("release", {}).get("steam_release_date")
            release_date_iso = datetime.fromtimestamp(release_ts, tz=timezone.utc).date() if release_ts else None

            basic_info = item.get("basic_info", {})
            publishers = ", ".join(p.get("name", "") for p in basic_info.get("publishers", []))[:255]
            developers = ", ".join(d.get("name", "") for d in basic_info.get("developers", []))[:255]
            category_ids = set(item.get("categories", {}).get("supported_player_categoryids", []))

            upsert_dim_game(cursor, (
                item["appid"], (item.get("name") or "Unknown Game")[:255],
                STORE_APP_TYPES.get(item.get("type"), str(item.get("type")))[:20],
                release_date_iso, is_free, price_vnd, publishers, developers,
                sum(1 for lang in item.get("supported_languages", []) if lang.get("supported")),
                bool(category_ids & MULTIPLAYER_CATEGORY_IDS),
                bool(category_ids & COOP_CATEGORY_IDS)
            ))
            processed_count += 1

    conn.commit()
    cursor.close()
    print(f"[Dimension Loader] Processed {processed_count} store browse items.")


def process_steamspy_dimensions(conn, client):
    cursor = conn.cursor()
    objects = client.list_objects(MINIO_BUCKET_NAME, prefix="steamspy/", recursive=True)
    print("[Dimension Loader] Processing SteamSpy Details...")

    processed_count = 0

    for obj in objects:
        payload = get_minio_json(client, obj.object_name)
        if not payload or not isinstance(payload, dict):
            continue

        game_id = payload.get("appid")
        if not game_id:
            continue

        positive = payload.get("positive", 0) or 0
        negative = payload.get("negative", 0) or 0
        total_reviews = positive + negative
        owners_min, owners_max = parse_owners(payload.get("owners"))

        cursor.execute(
            """
            UPDATE dim_game SET
                total_reviews = %s, positive = %s, negative = %s,
                owners_min = %s, owners_max = %s,
                avg_playtime_forever = %s, median_playtime_forever = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE game_id = %s;
            """,
            (total_reviews, positive, negative, owners_min, owners_max,
             payload.get("average_forever"), payload.get("median_forever"), game_id)
        )
        if cursor.rowcount == 0:
            continue  # chưa có trong dim_game -> bỏ qua, tránh vi phạm FK của bridge

        # Xung đột nguồn: SteamSpy trả genre dạng chuỗi "Action, Indie", Store trả mảng -> cùng vào dim_genre
        for genre_name in (payload.get("genre") or "").split(","):
            if genre_name.strip():
                upsert_genre(cursor, game_id, genre_name.strip())

        tags = payload.get("tags", {})
        if isinstance(tags, dict):
            for tag_name, vote_count in tags.items():
                tag_name_clean = str(tag_name).strip()
                if not tag_name_clean:
                    continue

                cursor.execute(
                    "INSERT INTO dim_tag (tag_name) VALUES (%s) ON CONFLICT (tag_name) DO NOTHING;",
                    (tag_name_clean,)
                )
                cursor.execute(
                    "SELECT tag_id FROM dim_tag WHERE tag_name = %s;",
                    (tag_name_clean,)
                )
                tag_row = cursor.fetchone()
                if tag_row:
                    tag_id = tag_row[0]
                    cursor.execute(
                        """
                        INSERT INTO bridge_game_tag (game_id, tag_id, vote_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (game_id, tag_id) DO UPDATE SET 
                            vote_count = EXCLUDED.vote_count,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        (game_id, tag_id, vote_count)
                    )
        processed_count += 1

    conn.commit()
    cursor.close()
    print(f"[Dimension Loader] Processed {processed_count} SteamSpy games.")


def run_dimension_update():
    conn = get_db_connection()
    client = get_minio_client()

    try:
        process_store_dimensions(conn, client)
        process_storebrowse_dimensions(conn, client)
        process_steamspy_dimensions(conn, client)
        print("[Dimension Loader] All dimensions processed successfully!")

    except Exception as e:
        print(f"[Dimension Loader] Error: {e}")
        conn.rollback()

    finally:
        if conn:
            conn.close()
            print("[Dimension Loader] Connection closed.")


if __name__ == "__main__":
    run_dimension_update()