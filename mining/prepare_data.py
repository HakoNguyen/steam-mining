"""
Task 6.1 - Đọc DWH thành DataFrame cho các mô hình khai phá.

    python mining/prepare_data.py   # in tóm tắt dữ liệu
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import get_db_connection

MIN_REVIEWS_FOR_RATIO = 50  # dưới ngưỡng này % positive không tin cậy -> NaN


def query_df(sql, params=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
    finally:
        conn.close()


def add_features(df):
    """Đặc trưng dẫn xuất; tách riêng để test được không cần DB."""
    df = df.copy()
    reviews = df["positive"] + df["negative"]
    df["positive_ratio"] = (df["positive"] / reviews).where(reviews >= MIN_REVIEWS_FOR_RATIO)
    df["owners_mid"] = (df["owners_min"] + df["owners_max"]) / 2
    # playtime 0 = SteamSpy không có số liệu, không phải "không ai chơi"
    for col in ["avg_playtime_forever", "median_playtime_forever"]:
        df[col] = df[col].where(df[col] > 0)
    # phân bố lệch rất mạnh -> log1p
    for col in ["avg_ccu", "peak_ccu", "owners_mid", "median_playtime_forever"]:
        df[f"log_{col}"] = np.log1p(df[col])
    df["release_month"] = pd.to_datetime(df["release_date_iso"]).dt.month
    return df


def load_games():
    """1 dòng/game: dim_game + CCU trung bình các ngày trong fact_daily_game_performance."""
    df = query_df("""
        SELECT g.game_id, g.game_title, g.release_date_iso, g.is_free, g.price_vnd::float AS price_vnd,
               g.publisher_name, g.developer_name, g.positive, g.negative,
               g.owners_min, g.owners_max, g.avg_playtime_forever, g.median_playtime_forever,
               g.languages_count, g.has_multiplayer, g.has_coop,
               f.avg_ccu, f.peak_ccu, COALESCE(f.snapshot_count, 0) AS snapshot_count
        FROM dim_game g
        LEFT JOIN (
            SELECT game_id, AVG(avg_ccu)::float AS avg_ccu, AVG(peak_ccu)::float AS peak_ccu,
                   SUM(snapshot_count) AS snapshot_count
            FROM fact_daily_game_performance
            GROUP BY game_id
        ) f USING (game_id)
        WHERE g.app_type = 'game'
    """)
    num_cols = ["positive", "negative", "owners_min", "owners_max", "avg_playtime_forever",
                "median_playtime_forever", "languages_count", "avg_ccu", "peak_ccu"]
    df[num_cols] = df[num_cols].astype(float)
    return add_features(df).set_index("game_id")


def load_tag_transactions(top_k=10):
    """{game_id: [tag, ...]} - top_k tag nhiều vote nhất mỗi game (giảm nhiễu tag lẻ)."""
    df = query_df("""
        SELECT game_id, tag_name FROM (
            SELECT b.game_id, t.tag_name,
                   ROW_NUMBER() OVER (PARTITION BY b.game_id ORDER BY b.vote_count DESC, t.tag_name) AS rn
            FROM bridge_game_tag b
            JOIN dim_tag t USING (tag_id)
            JOIN dim_game g USING (game_id)
            WHERE g.app_type = 'game'
        ) x
        WHERE rn <= %s
    """, (top_k,))
    return df.groupby("game_id")["tag_name"].apply(list).to_dict()


def load_genres():
    """One-hot genre, index game_id."""
    df = query_df("""
        SELECT b.game_id, gr.genre_name
        FROM bridge_game_genre b JOIN dim_genre gr USING (genre_id)
    """)
    return pd.crosstab(df["game_id"], df["genre_name"]).clip(upper=1)


if __name__ == "__main__":
    games = load_games()
    print(f"{len(games)} game; không thiếu: ")
    print(games.notna().sum().to_string())
    print(f"\npositive_ratio: {games['positive_ratio'].describe().round(3).to_dict()}")
    tx = load_tag_transactions()
    print(f"\n{len(tx)} giao dịch tag, trung bình {np.mean([len(t) for t in tx.values()]):.1f} tag/game")
    genres = load_genres()
    print(f"{genres.shape[1]} genre: {genres.sum().sort_values(ascending=False).head(10).to_dict()}")
