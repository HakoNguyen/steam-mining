"""
Task 6.1 - Đọc warehouse (SQLMesh: marts, dw) thành DataFrame cho các mô hình khai phá; ghi kết quả vào schema mining.
Tập dữ liệu: ~2.000 game nhiều owners nhất (is_in_universe), chỉ app_type = 'game'.

    python mining/prepare_data.py   # in tóm tắt dữ liệu
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import URL, create_engine, text

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation import db_connect as db

ENGINE = create_engine(URL.create("postgresql+psycopg2", username=db.DB_USER, password=db.DB_PASS,
                                  host=db.DB_HOST, port=int(db.DB_PORT), database=db.DB_NAME))
UNIVERSE = "f.is_in_universe AND f.app_type = 'game'"


def query_df(sql, **params):
    return pd.read_sql(text(sql), ENGINE, params=params)


def save_table(df, name, dtype=None):
    """Ghi đè bảng mining.<name>; copilot_ro tự có quyền SELECT (default privileges trong create_copilot_role.sql)."""
    with ENGINE.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS mining"))
        df.to_sql(name, conn, schema="mining", if_exists="replace", index=False, dtype=dtype)


def add_features(df):
    """Game miễn phí giá 0; game trả phí không bán ở VN (price_vnd NULL) để NaN, không coi là giá 0 như log_price của mart."""
    price = df["price_vnd"].where(~df["is_free"].eq(True), 0.0)
    return df.assign(price_vnd=price, log_price=np.log1p(price))


def load_games():
    """1 dòng/game từ marts.mart_mining_features (positive_ratio chỉ có khi >= 50 review)."""
    df = query_df(f"""
        SELECT game_id, game_title, release_date, release_month, is_free, price_vnd::float AS price_vnd,
               publisher_name, developer_name, publisher_prior_games, num_languages, is_multiplayer, is_coop,
               owners_min, owners_max, owners_mid::float AS owners_mid, positive_reviews, negative_reviews,
               total_reviews, positive_ratio::float AS positive_ratio, is_high_positive,
               avg_ccu::float AS avg_ccu, peak_ccu::float AS peak_ccu, snapshot_count, log_owners, log_avg_ccu
        FROM marts.mart_mining_features AS f
        WHERE {UNIVERSE}
    """)
    return add_features(df).set_index("game_id")


def load_tag_transactions(top_k=10):
    """{game_id: [tag, ...]} - top_k tag nhiều vote nhất mỗi game (giảm nhiễu tag lẻ)."""
    df = query_df(f"""
        SELECT b.game_id, t.tag_name
        FROM dw.bridge_game_tag AS b
        JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
        JOIN marts.mart_mining_features AS f ON f.game_id = b.game_id
        WHERE b.vote_rank <= :top_k AND {UNIVERSE}
    """, top_k=top_k)
    return df.groupby("game_id")["tag_name"].apply(list).to_dict()


def load_genres():
    """One-hot thể loại (SteamSpy genre), index game_id."""
    df = query_df(f"""
        SELECT b.game_id, g.genre_name
        FROM dw.bridge_game_genre AS b
        JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
        JOIN marts.mart_mining_features AS f ON f.game_id = b.game_id
        WHERE {UNIVERSE}
    """)
    return pd.crosstab(df["game_id"], df["genre_name"]).clip(upper=1)


def load_reviews():
    """Review tiếng Anh đã khử trùng (dw.fact_game_reviews): game_id, text, voted_up (1 khen / 0 chê)."""
    return query_df("""
        SELECT review_id, game_id, review_text AS text, voted_up::int AS voted_up
        FROM dw.fact_game_reviews
        WHERE review_text IS NOT NULL
    """).set_index("review_id")


if __name__ == "__main__":
    games = load_games()
    print(f"{len(games)} game; không thiếu:")
    print(games.notna().sum().to_string())
    print(f"\npositive_ratio: {games['positive_ratio'].describe().round(3).to_dict()}")
    tx = load_tag_transactions()
    print(f"\n{len(tx)} giao dịch tag, trung bình {np.mean([len(t) for t in tx.values()]):.1f} tag/game")
    genres = load_genres()
    print(f"{genres.shape[1]} thể loại: {genres.sum().sort_values(ascending=False).head(10).to_dict()}")
    reviews = load_reviews()
    print(f"{len(reviews)} review, {reviews['voted_up'].mean():.1%} khen")
