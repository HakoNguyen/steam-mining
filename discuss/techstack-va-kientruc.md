# Tài Liệu Thiết Kế Tech Stack & Cấu Hình Docker (Steam Data Warehouse)

---

## I. BẢNG DANH SÁCH TECH STACK CHÍNH THỨC

| Tầng chức năng | Công nghệ lựa chọn | Ghi chú & Cổng dịch vụ |
|---|---|---|
| **L1: Raw Data Lake** | **MinIO (S3-Compatible)** | Container `steam_minio_lake` (API `9000`, Web UI `9001`) |
| **L2: Data Warehouse Engine** | **PostgreSQL 16** | Container `steam_postgres_dwh` (Port `5432`) |
| **ETL Orchestrator & Scheduler** | **Apache Airflow 2.8+** | Container `steam_apache_airflow` (Port `8080`) |
| **Data Transformation** | **SQLMesh** | Tích hợp trực tiếp vào Airflow & PostgreSQL |
| **L3: BI Dashboard (Kéo-Thả)** | **Metabase BI** | Container `steam_metabase_bi` (Port `3000`) |
| **AI Copilot & Text-to-SQL UI** | **Streamlit** | Container `steam_streamlit_copilot` (Port `8501`) |
| **Đóng gói & Triển khai** | **Docker Compose** | Mạng nội bộ Container `steam_dwh_net` |

---

## II. SƠ ĐỒ KIẾN TRÚC DOCKER COMPOSE (5 CONTAINERS)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
|                                DOCKER COMPOSE NETWORK                                  |
|                                  (`steam_dwh_net`)                                     |
|                                                                                        |
|  ┌───────────────────────┐   ┌───────────────────────┐   ┌──────────────────────────┐  |
|  │    minio-datalake     │   │    postgres-dwh       │   │    apache-airflow     │  |
|  │ (Raw S3 Object Store) │   │  (PostgreSQL 16 DWH)  │   │  (ETL & Orchestrator) │  |
|  │ Ports: 9000 / 9001    │   │   Port: 5432          │   │   Port: 8080          │  |
|  └───────────────────────┘   └───────────────────────┘   └──────────────────────────┘  |
|              │                           ▲                             │               |
|              └───────────────────────────┼─────────────────────────────┘               |
|                                          │                                             |
|              ┌───────────────────────────┴───────────────────────────┐                 |
|              │                                                       │                 |
|  ┌───────────────────────┐                               ┌──────────────────────────┐  |
|  │      metabase-bi      │                               │    streamlit-copilot     │  |
|  │ (Drag & Drop Dashboard│                               │(SQL Assistant & BERTopic)│  |
|  │   Port: 3000          │                               │    Port: 8501            │  |
|  └───────────────────────┘                               └──────────────────────────┘  |
└────────────────────────────────────────────────────────────────────────────────────────┘
```

> **Phạm vi Container Streamlit Copilot (Port 8501):** Được định vị là giao diện Trợ lý Phân tích SQL cho giảng viên & hội đồng. Nhập câu hỏi tự nhiên ➔ Sinh truy vấn SQL tương ứng trên `steam_dwh` ➔ Hiển thị biểu đồ Metabase nhúng và trực quan hóa kết quả gom nhóm phàn nàn BERTopic.

---

## III. DDL SCRIPT KHO DỮ LIỆU (POSTGRESQL STAR SCHEMA)

```sql
-- =============================================================================
-- 1. Schema Raw JSONB (Raw Staging Area)
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
-- 2. Dimensions & Bridge Tables
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
    primary_genre VARCHAR(50),                     -- Genre đầu tiên làm căn cứ phân Top 25%
    total_reviews INT DEFAULT 0,                   -- Tổng review tích lũy (Nguồn: Steam Web Reviews API)
    tier_code VARCHAR(10) DEFAULT 'UNTIERED',      -- 'TOP_300', 'MID_2000', 'TAIL_3000'
    sample_hour SMALLINT DEFAULT 0,                -- Gán ngẫu nhiên 0-23 để rải đều tải lấy mẫu
    is_unreleased BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_tag (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) UNIQUE NOT NULL,
    is_genre_overlap BOOLEAN DEFAULT FALSE         -- TRUE cho các tag trùng tên với 13-16 Genre cơ bản
);

CREATE TABLE IF NOT EXISTS bridge_game_tag (
    game_id INT REFERENCES dim_game(game_id),
    tag_id INT REFERENCES dim_tag(tag_id),
    vote_count INT NOT NULL DEFAULT 0,
    vote_share NUMERIC(5,4),
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
    is_weekend BOOLEAN,
    is_sale_period BOOLEAN DEFAULT FALSE,           -- Cờ sự kiện Steam Sale
    sale_event_name VARCHAR(50) NULL                -- Ví dụ: 'Autumn Sale 2026'
);

CREATE TABLE IF NOT EXISTS dim_time (
    time_key INT PRIMARY KEY,                       -- HHMM
    hour_utc INT NOT NULL,                          -- 0 - 23
    minute_utc INT NOT NULL,
    day_part VARCHAR(20)
);

-- =============================================================================
-- 3. Fact Tables (Dual-Grain Fact Architecture)
-- =============================================================================

-- Fact 1: Snapshot chi tiết theo giờ (Grain: 1 snapshot / mốc lấy mẫu) - Phục vụ Top 300 game Realtime Trend
CREATE TABLE IF NOT EXISTS fact_player_snapshot (
    game_id INT REFERENCES dim_game(game_id),
    date_key INT REFERENCES dim_date(date_key),
    time_key INT REFERENCES dim_time(time_key),
    snapshot_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    concurrent_players INT DEFAULT 0,
    price_vnd NUMERIC(12, 2) DEFAULT 0.00,
    discount_percent INT DEFAULT 0,
    positive_reviews BIGINT DEFAULT 0,
    negative_reviews BIGINT DEFAULT 0,
    owners_min BIGINT DEFAULT 0,
    owners_max BIGINT DEFAULT 0,
    PRIMARY KEY (game_id, date_key, time_key)
);

-- Fact 2: Aggregate Fact theo Ngày (Grain: 1 game / 1 ngày) - Phục vụ OLAP, Metabase, K-Means & CART Tree
CREATE TABLE IF NOT EXISTS fact_daily_game_performance (
    date_key INT REFERENCES dim_date(date_key),
    game_id INT REFERENCES dim_game(game_id),
    tier_code VARCHAR(10) NOT NULL DEFAULT 'UNTIERED',
    peak_ccu INT NOT NULL,                          -- Chỉ so sánh giữa các game cùng tier_code
    avg_ccu NUMERIC(12,2) NOT NULL,                 -- Độ đo dùng cho K-Means / CART Tree
    min_ccu INT NOT NULL,
    snapshot_count SMALLINT NOT NULL,               -- 24 (Top), 4 (Mid), 1 (Tail)
    fetch_error_count SMALLINT DEFAULT 0,            -- Audit lỗi 429 / connection drop
    price_vnd NUMERIC(12,2),
    discount_pct SMALLINT,
    price_as_of_date DATE NULL,                     -- Theo dõi độ tươi của giá
    PRIMARY KEY (date_key, game_id)
);

-- =============================================================================
-- 4. Data Mart View cho Khai Phá Dữ Liệu (Apriori & FP-Growth)
-- =============================================================================
CREATE OR REPLACE VIEW mart_apriori_transactions AS
SELECT 
    game_id, 
    ARRAY_AGG(tag_name ORDER BY r ASC) AS transaction_items
FROM (
    SELECT 
        b.game_id, 
        t.tag_name,
        ROW_NUMBER() OVER (
            PARTITION BY b.game_id 
            ORDER BY b.vote_count DESC, t.tag_name ASC
        ) AS r
    FROM bridge_game_tag b
    JOIN dim_tag t ON b.tag_id = t.tag_id
    JOIN dim_game g ON b.game_id = g.game_id
    WHERE NOT t.is_genre_overlap             -- 1. Lọc bỏ Stop-list trùng Genre trước
      AND g.app_type = 'game' 
      AND g.total_reviews >= 50              -- 2. Lọc loại game rác
) ranked_tags
WHERE r <= 10                                 -- 3. Top-N cố định (N=10)
GROUP BY game_id 
HAVING COUNT(*) >= 3;
```

---

## IV. CẤU HÌNH DOCKER COMPOSE (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  # Container 1: PostgreSQL Data Warehouse Engine (Phân tách 3 DBs)
  postgres-dwh:
    image: postgres:16-alpine
    container_name: steam_postgres_dwh
    restart: always
    environment:
      POSTGRES_DB: steam_dwh
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: adminpassword123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_databases.sql:/docker-entrypoint-initdb.d/init_databases.sql
    networks:
      - steam_dwh_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d steam_dwh"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Container 2: MinIO Object Storage (L1 Raw Data Lake S3)
  minio-datalake:
    image: minio/minio:latest
    container_name: steam_minio_lake
    restart: always
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: miniopassword123
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    networks:
      - steam_dwh_net

  # Container 3.1: Airflow Init (One-shot Init DB Container)
  airflow-init:
    image: apache/airflow:2.8.1-python3.11
    container_name: steam_airflow_init
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://admin:adminpassword123@postgres-dwh:5432/airflow_db
      - AIRFLOW__CORE__FERNET_KEY=46BKJgYlLwV8W0_pAKo5i3WzAZ0_J8x0v1Z23456789=
    depends_on:
      postgres-dwh:
        condition: service_healthy
    command: bash -c "airflow db init && airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com"
    networks:
      - steam_dwh_net

  # Container 3.2: Apache Airflow Webserver & Scheduler
  apache-airflow:
    image: apache/airflow:2.8.1-python3.11
    container_name: steam_apache_airflow
    restart: always
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://admin:adminpassword123@postgres-dwh:5432/airflow_db
      - AIRFLOW__CORE__FERNET_KEY=46BKJgYlLwV8W0_pAKo5i3WzAZ0_J8x0v1Z23456789=
      - AIRFLOW__CORE__LOAD_EXAMPLES=False
    ports:
      - "8080:8080"
    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
    depends_on:
      airflow-init:
        condition: service_completed_successfully
    command: bash -c "airflow webserver & airflow scheduler"
    networks:
      - steam_dwh_net

  # Container 4: Metabase BI (Trỏ vào metabase_db riêng)
  metabase-bi:
    image: metabase/metabase:latest
    container_name: steam_metabase_bi
    restart: always
    ports:
      - "3000:3000"
    environment:
      MB_DB_TYPE: postgres
      MB_DB_DBNAME: metabase_db
      MB_DB_PORT: 5432
      MB_DB_USER: admin
      MB_DB_PASS: adminpassword123
      MB_DB_HOST: postgres-dwh
    depends_on:
      postgres-dwh:
        condition: service_healthy
    networks:
      - steam_dwh_net

  # Container 5: Streamlit (Trợ lý AI Copilot UI)
  streamlit-copilot:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    container_name: steam_streamlit_copilot
    restart: always
    ports:
      - "8501:8501"
    environment:
      POSTGRES_HOST: postgres-dwh
      POSTGRES_DB: steam_dwh
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: adminpassword123
      OPENAI_API_KEY: ${OPENAI_API_KEY:-""}
    depends_on:
      postgres-dwh:
        condition: service_healthy
    networks:
      - steam_dwh_net

networks:
  steam_dwh_net:
    driver: bridge

volumes:
  minio_data:
  postgres_data:
```

---

## V. CỔNG TRUY CẬP VÀ LỆNH KHỞI CHẠY

```bash
# Khởi chạy toàn bộ hệ thống bằng 1 lệnh duy nhất:
docker-compose up -d --build
```

* 🪣 **MinIO S3 Data Lake Console:** `http://localhost:9001` (User: `admin` / Pass: `miniopassword123`)
* ⚙️ **Apache Airflow (ETL Scheduler):** `http://localhost:8080` (User: `admin` / Pass: `admin`)
* 📊 **Metabase BI (Dashboard Kéo-Thả):** `http://localhost:3000`
* 🤖 **Streamlit (AI Copilot Chatbot):** `http://localhost:8501`
* 🗄️ **PostgreSQL Database:** `localhost:5432` (Database: `steam_dwh`)

---

## VI. GIẢ ĐỊNH CHƯA KIỂM CHỨNG (UNVERIFIED ASSUMPTIONS)

Các điểm kỹ thuật cần thực nghiệm kiểm chứng bằng data thu thập thực tế:

1. **Tỷ lệ game có Tag từ SteamSpy:** SteamSpy API `appdetails` trả về dict `tags`. Cần chạy Audit thực tế để xác định % game trong Top 5.000 trả về tag rỗng `[]` để đánh giá rủi ro ảnh hưởng tới Apriori.
2. **Rate Limit thực tế của SteamSpy:** Giới hạn lý thuyết là 1 request/giây. Cần đo kiểm độ ổn định trong DAG Weekly khi crawl 5.000 games.
3. **Định dạng tiền tệ VNĐ từ Steam Store:** Giả định `price_overview.final` từ `appdetails?cc=vn` trả về mệnh giá VNĐ dưới dạng cents ($\times 100$). Cần kiểm chứng với các game Free to Play và game có gói giảm giá đặc biệt.
4. **Phân bố Modulo modulo `game_id % 24`:** Số hiệu `appid` của Steam cấp theo lô (batch). Việc áp dụng `sample_hour = ROW_NUMBER() OVER (ORDER BY random()) % 24` khi re-tiering là bắt buộc để đảm bảo độ phẳng của tải.
5. **Nguồn dữ liệu chuẩn cho `total_reviews`:** `store.steampowered.com/api/appdetails` không trả về tổng số review (chỉ có `recommendations.total`). Nguồn chính thức được chọn cho `dim_game.total_reviews` là **Steam Web Reviews API (`query_summary.total_reviews`)** với fallback là `SteamSpy (positive + negative)`.
