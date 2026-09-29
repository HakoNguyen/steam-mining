import duckdb
import os

# 1. Đường dẫn file database DuckDB dùng chung
DB_PATH = r"d:\DE\projects\DWH-DM\steam_lake.duckdb"

def init_duckdb_views():
    con = duckdb.connect(DB_PATH)
    
    # 2. Cài đặt và nạp extension HTTPFS để kết nối MinIO S3
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    
    # 3. Khai báo Secret xác thực S3 MinIO
    con.execute("""
        CREATE OR REPLACE SECRET minio (
            TYPE s3,
            KEY_ID 'admin',
            SECRET 'adminpassword123',
            ENDPOINT 'localhost:9000',
            USE_SSL false,
            URL_STYLE 'path'
        );
    """)
    
    # 4. Tạo các Views truy vấn trực tiếp trên Hồ dữ liệu MinIO S3
    con.execute("""
        CREATE OR REPLACE VIEW v_steamspy_raw AS 
        SELECT name, appid, owners, average_forever, median_forever, tags 
        FROM read_json_auto('s3://raw-steam-data/steamspy/*/*/*/*.json');
    """)
    
    con.execute("""
        CREATE OR REPLACE VIEW v_reviews_raw AS 
        SELECT query_summary.review_score_desc, query_summary.total_positive, 
        query_summary.total_negative, query_summary.total_reviews 
        FROM read_json_auto('s3://raw-steam-data/reviews/*/*/*/*.json');
    """)
    
    con.execute("""
        CREATE OR REPLACE VIEW v_store_games_parquet AS 
        SELECT * FROM read_parquet('s3://raw/steam/store_games.parquet');
    """)
    
    con.execute("""
        CREATE OR REPLACE VIEW v_game_stats_parquet AS 
        SELECT * FROM read_parquet('s3://raw/steam/game_stats.parquet');
    """)
    
    con.close()
    print(f"✅ Đã khởi tạo thành công các Views trong file DuckDB: {DB_PATH}")

if __name__ == "__main__":
    init_duckdb_views()
