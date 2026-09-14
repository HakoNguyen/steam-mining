-- =============================================================================
-- 1. Raw Staging Schema (Tầng Staging nạp dữ liệu thô JSONB từ MinIO S3)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.steam_games_json (
    appid INT PRIMARY KEY,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    payload JSONB
);

CREATE TABLE IF NOT EXISTS raw.steam_reviews_json (
    review_id VARCHAR(50) PRIMARY KEY,
    appid INT,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    payload JSONB
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
