-- =============================================================================
-- 1. Raw Staging Schema (Tầng Staging nạp dữ liệu thô JSONB từ MinIO S3)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS raw;

-- Mỗi file JSON trên MinIO = 1 dòng (transformation/load_raw.py nạp tăng dần theo partition ngày).
-- Cùng cấu trúc cho 4 nguồn: steam_store_json, steam_steamspy_json, steam_ccu_json, steam_reviews_json
CREATE TABLE IF NOT EXISTS raw.steam_store_json (
    object_key VARCHAR(255) PRIMARY KEY,                 -- store/year=YYYY/month=MM/day=DD/store_<appid>_<ts>.json
    appid INT NOT NULL,
    partition_date DATE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,       -- parse từ timestamp trong tên file (UTC)
    payload JSONB NOT NULL,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS raw.steam_steamspy_json (LIKE raw.steam_store_json INCLUDING ALL);
CREATE TABLE IF NOT EXISTS raw.steam_ccu_json (LIKE raw.steam_store_json INCLUDING ALL);
CREATE TABLE IF NOT EXISTS raw.steam_reviews_json (LIKE raw.steam_store_json INCLUDING ALL);

-- Watermark: ngày partition cuối cùng đã nạp cho từng nguồn
CREATE TABLE IF NOT EXISTS raw.load_watermark (
    source VARCHAR(50) PRIMARY KEY,                     -- store | steamspy | ccu | reviews
    last_partition_date DATE NOT NULL,
    files_loaded INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Daily Seed List: snapshot Top 50 game mỗi ngày (ingestion/catalog.py ghi, mọi DAG đọc chung)
CREATE TABLE IF NOT EXISTS raw.game_catalog_daily (
    catalog_date DATE NOT NULL,
    ranking_order INT NOT NULL,
    game_id INT NOT NULL,
    game_title VARCHAR(255),
    ccu_2weeks INT,
    source VARCHAR(50) DEFAULT 'steamspy_top100in2weeks',  -- 'carry_over' | 'fallback' khi API lỗi
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (catalog_date, game_id)
);

-- =============================================================================
-- 2. Dimensions & Bridge Tables (Tầng Chiều dữ liệu DWH Star Schema)
-- =============================================================================
CREATE TABLE IF NOT EXISTS dim_game (
    game_id INT PRIMARY KEY,
    game_title VARCHAR(255) NOT NULL,
    app_type VARCHAR(20) DEFAULT 'game',          -- 'game', 'dlc', 'mod'
    release_date_iso DATE,
    is_free BOOLEAN DEFAULT FALSE,
    price_vnd NUMERIC(12, 2) DEFAULT 0.00,
    publisher_name VARCHAR(255),
    developer_name VARCHAR(255),
    total_reviews INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dim_tag (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_game_tag (
    game_id INT REFERENCES dim_game(game_id),
    tag_id INT REFERENCES dim_tag(tag_id),
    vote_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, tag_id)
);

CREATE TABLE IF NOT EXISTS dim_genre (
    genre_id SERIAL PRIMARY KEY,
    genre_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_game_genre (
    game_id INT REFERENCES dim_game(game_id),
    genre_id INT REFERENCES dim_genre(genre_id),
    PRIMARY KEY (game_id, genre_id)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT PRIMARY KEY,                       -- YYYYMMDD
    full_date DATE NOT NULL,
    day_of_week INT,                                -- 1 = Monday, 7 = Sunday
    month INT,
    quarter INT,
    year INT,
    is_weekend BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_time (
    time_key INT PRIMARY KEY,                       -- HHMM
    hour_utc INT NOT NULL,                          -- 0 - 23
    minute_utc INT NOT NULL,
    day_part VARCHAR(20)
);

-- =============================================================================
-- 3. Dual-Grain Fact Tables (Tầng Sự kiện)
-- =============================================================================

-- Fact 1: Snapshot chi tiết theo giờ (CCU Realtime Trend)
CREATE TABLE IF NOT EXISTS fact_player_snapshot (
    game_id INT REFERENCES dim_game(game_id),
    date_key INT REFERENCES dim_date(date_key),
    time_key INT REFERENCES dim_time(time_key),
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    concurrent_players INT DEFAULT 0,
    price_vnd NUMERIC(12, 2) DEFAULT 0.00,
    discount_percent INT DEFAULT 0,
    PRIMARY KEY (game_id, date_key, time_key)
);

-- Fact 2: Tổng hợp theo ngày (Phục vụ OLAP, Metabase, K-Means & CART Tree)
CREATE TABLE IF NOT EXISTS fact_daily_game_performance (
    date_key INT REFERENCES dim_date(date_key),
    game_id INT REFERENCES dim_game(game_id),
    peak_ccu INT NOT NULL,
    avg_ccu NUMERIC(12,2) NOT NULL,
    min_ccu INT NOT NULL,
    snapshot_count SMALLINT NOT NULL,
    price_vnd NUMERIC(12,2),
    discount_pct SMALLINT,
    PRIMARY KEY (date_key, game_id)
);
