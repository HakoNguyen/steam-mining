-- =============================================================================
-- Raw Staging Schema (Tầng Staging nạp dữ liệu thô JSONB từ MinIO S3)
-- Các tầng phía sau (staging, dw, marts) do SQLMesh tạo và quản lý: xem thư mục sqlmesh/models/
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
-- IStoreBrowseService: 1 file = 1 batch 50 game, appid = game đầu batch (tập ~2.000 game Mining)
CREATE TABLE IF NOT EXISTS raw.steam_storebrowse_json (LIKE raw.steam_store_json INCLUDING ALL);

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
    ccu_2weeks INT,                                     -- thực chất là CCU đỉnh hôm qua theo SteamSpy (staging đổi tên thành ccu_peak_yesterday)
    source VARCHAR(50) DEFAULT 'steamspy_top100in2weeks',  -- 'carry_over' | 'fallback' khi API lỗi
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (catalog_date, game_id)
);

-- Game Universe: ~2.000 game nhiều owners nhất (SteamSpy request=all), chụp mỗi tuần cho Data Mining (ingestion/universe.py)
CREATE TABLE IF NOT EXISTS raw.game_universe (
    snapshot_date DATE NOT NULL,
    owners_rank INT NOT NULL,
    game_id INT NOT NULL,
    game_title VARCHAR(255),
    owners_range VARCHAR(50),
    source VARCHAR(50) DEFAULT 'steamspy_all',             -- 'carry_over' khi API lỗi
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, game_id)
);
