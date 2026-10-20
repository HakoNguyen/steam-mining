# 📝 NHẬT KÝ TIẾN ĐỘ & LỊCH SỬ THẢO LUẬN DỰ ÁN (STEAM DWH & DATA MINING)

> **Mục đích:** Lưu trữ toàn bộ tiến độ công việc, quyết định kỹ thuật, thông số hệ thống và roadmap từng bước để đảm bảo không bị mất dấu ngữ cảnh khi làm việc.

---

## 📌 1. THÔNG TIN DỰ ÁN & THÔNG SỐ HỆ THỐNG

* **Tên đề tài:** Xây dựng kho dữ liệu và khai phá dữ liệu thị trường game trên nền tảng Steam
* **GitHub Repository:** `https://github.com/HakoNguyen/steam-mining.git`
* **Nhánh làm việc chính:** `feat/01` (đã sync với `main`)

### 🌐 Thông số Docker Containers & Cổng truy cập (Local):
* 🗄️ **PostgreSQL 16 (DWH):** `localhost:5433` (trong Docker network: `postgres-dwh:5432`) | DB main: `steam_dwh` | DB phụ: `airflow_db`, `metabase_db` (User: `admin` / Pass: `adminpassword123`)
* 🪣 **MinIO S3 Data Lake:** API `localhost:9000` | Web UI `http://localhost:9001` (User: `admin` / Pass: `adminpassword123`) | Bucket: `raw-steam-data`
* ⚙️ **Apache Airflow:** `http://localhost:8080` (User: `admin` / Pass: `admin`)
* 📊 **Metabase BI:** `http://localhost:3000`

---

## 🗺️ 2. TIẾN ĐỘ THỰC HIỆN (LỘ TRÌNH 6 PHASE)

```
[x] Phase 0: Thiết lập Nền móng & Git Flow
    ├── Đặt kiến trúc thư mục DE chuẩn (discuss/, scripts/, ingestion/, dags/, mining/, docs/)
    ├── Cấu hình .gitignore, .env.example, .env (không commit secret & cache)
    ├── Tạo requirements.txt tối ưu nhẹ gọn (curl-cffi, requests, pandas, psycopg2-binary, sqlmesh)
    └── Push README.md kèm sơ đồ Data Flow Visual & Icons lên GitHub main

[x] Phase 1: Dựng Hạ tầng Docker Engine & Databases
    ├── Tạo script scripts/init_databases.sql (khởi tạo airflow_db & metabase_db)
    ├── Xây dựng docker-compose.yml 4 services (Postgres, MinIO, Airflow, Metabase)
    └── Bật thành công 4 Containers xanh (Healthy & Running)

[x] Phase 2: Khởi tạo Schema & Data Lake Storage
    ├── [x] Tạo Bucket 'raw-steam-data' trên MinIO Console (port 9001)
    └── [x] Viết DDL Star Schema scripts/create_dwh_schema.sql (Raw JSONB, Dimensions, Facts, Bridge)

[x] Phase 3: Module Ingestion & Airflow DAGs
    ├── [x] collector.py (curl_cffi, retry) ghi JSON thô vào MinIO, partition year=/month=/day=
    ├── [x] DAGs: Hourly CCU, Daily Metadata (Store + SteamSpy), Daily Reviews
    └── [x] (15/10) Dynamic Daily Catalog Top 50: raw.game_catalog_daily + DAG steam_daily_catalog_sync

[x] Phase 4: Transformation & ELT Pipeline (Raw ➔ DWH)
    ├── [x] (15/10) Nạp JSONB từ MinIO vào schema raw (incremental theo partition ngày + watermark, gồm reviews)
    └── [x] (16/10) SQLMesh: 7 staging + 12 dw (dim_game SCD2, fact incremental) + 4 marts, audits; chạy trong Airflow

[ ] Phase 5: Khai phá dữ liệu (Data Mining)
    ├── Apriori / FP-Growth (Luật kết hợp Tag game)
    ├── K-Means Clustering (Phân tầng thị trường)
    └── Decision Tree CART (Dự đoán game hit)

[ ] Phase 6: Dashboard & Streamlit Copilot UI
```

---

## 📜 3. TỔNG HỢP NHẬT KÝ CHI TIẾT TỪNG BƯỚC

### 🔹 Bước 0: PoC & Khảo sát API
* Crawl thành công dữ liệu mẫu thực tế từ cả 4 API Steam cho game `Cyberpunk 2077` (AppID: `1091500`) lưu vào `steam_sample_data.json`.
* Phát hiện và xử lý bài toán Cloudflare/Akamai blocking trên `store.steampowered.com` bằng thư viện `curl_cffi` (impersonate `chrome124`).

### 🔹 Bước 1: Hạ tầng Docker & Fix lỗi phát sinh
* Phát hiện lỗi `Connection reset` và Docker Windows tự tạo nhầm directory cho file script `.sql`.
* Đã clean volume (`docker-compose down -v`) và đổi tên chuẩn file [scripts/init_databases.sql](file:///d:/DE/projects/DWH-DM/scripts/init_databases.sql).
* Khởi chạy thành công 4 services, Postgres báo `healthy`.

### 🔹 Bước 2 (15/10/2026): Dọn dẹp & Dynamic Daily Catalog (Giai đoạn 1 của kế hoạch chuẩn hóa)
* Xóa file rác: `steam_lake.duckdb`, `scripts/init_duckdb_views.py`, `ingestion/raw_ccu.db`, thư mục rỗng `dags/transform_/`.
* **Quyết định:** bảng catalog đặt ở `raw.game_catalog_daily` (không phải `public.dim_game_catalog_daily`) vì là dữ liệu nguồn do Python ghi; SQLMesh sau này đọc như source.
* `ingestion/catalog.py`: lấy SteamSpy `top100in2weeks`, sắp theo `ccu` giảm dần, giữ Top 50. API lỗi ➔ copy snapshot gần nhất (`carry_over`), chưa có ➔ danh sách cứng (`fallback`). Có advisory lock, chạy lại không nhân bản.
* `get_target_appids()` đọc catalog; nếu hôm nay chưa có snapshot thì tự sync. CCU nay dùng đủ 50 game (trước là 20).
* DAG metadata chuyển từ `@weekly` sang `@daily` để game mới vào Top 50 có metadata trong ngày.
* `load_facts.py` lấy tên game từ catalog thay cho placeholder `"AppID xxx"`; đã backfill 3 game ma cũ.
* Dữ liệu trước 15/10 coi là dữ liệu test.

### 🔹 Bước 3 (15/10/2026): Tầng Raw Staging (Giai đoạn 2)
* `transformation/load_raw.py`: MinIO ➔ `raw.steam_{store,steamspy,ccu,reviews}_json` (1 file = 1 dòng, khóa `object_key`, có `appid`, `partition_date`, `fetched_at` parse từ tên file).
* Incremental: `raw.load_watermark` lưu ngày partition cuối của từng nguồn; mỗi lần chỉ duyệt các partition `>= watermark` (duyệt prefix year=/month=/day= không recursive), bỏ qua key đã có.
* Bỏ 2 bảng raw cũ không dùng (`raw.steam_games_json`, `raw.steam_reviews_json` dạng 1 review/dòng).
* Loader dim/fact cũ chuyển sang đọc từ `raw.*` ➔ **không còn full scan MinIO**. Store/SteamSpy chỉ lấy payload mới nhất mỗi game. `run_dimension_update` giờ raise lỗi để Airflow báo FAILED.
* DAG transform: `task_load_raw >> task_transform_dimensions >> task_transform_facts`.
* Kết quả lần đầu: store 109, steamspy 107, ccu 1207, reviews 231 file — khớp 100% với MinIO; lần chạy lại nạp 0 file.
* Ghi nhận: Reviews API trả cùng ~50 review "hữu ích nhất" mỗi ngày ➔ hiện chỉ có 2.664 review khác nhau / 51 game.

### 🔹 Bước 4 (16/10/2026): Collector báo lỗi đúng khi mạng tới Steam bị chặn
* Sự cố: nhà mạng chặn kết nối tới `*.steampowered.com` (reset ở bước TLS, SteamSpy vẫn vào được) ➔ mất ~1/3 dữ liệu mà Airflow vẫn báo xanh. Xử lý mạng: bật Cloudflare WARP.
* `collector.py`: `collect_*` trả True/False; `collect_batch` thử lại riêng game lỗi sau 30s, in tổng kết `X/50 OK`, raise nếu < 80% ➔ task FAILED và Airflow tự retry. Retry backoff 2s/4s cho cả lỗi mạng và HTTP != 200.
* Store API thêm `cc=vn` ➔ giá luôn là VND.

### 🔹 Bước 5 (16/10/2026): Chuyển transformation sang SQLMesh (Giai đoạn 3)
* SQLMesh 0.236.3: cài ở `.venv` (dev trên Windows) và venv riêng `/opt/sqlmesh-venv` trong image Airflow (`Dockerfile`), không cài chung với Airflow vì xung đột `duckdb`. Tích hợp Airflow sẵn có của SQLMesh đã bị gỡ ➔ dùng `BashOperator` gọi `sqlmesh --gateway docker run`.
* `sqlmesh/config.yaml`: 2 gateway trỏ cùng database (`local` = localhost:5433, `docker` = postgres-dwh:5432); mật khẩu đọc từ `sqlmesh/.env` (không commit); `start: 2026-10-15` (dữ liệu trước đó coi là chạy thử).
* Schema: `staging` (VIEW làm sạch JSON), `dw` (star schema), `marts` (phục vụ Metabase/Mining). Không dùng `public` vì SQLMesh không ghi đè được bảng tạo tay.
* Kiểu lưu: `dim_game` **SCD Type 2 by column** (giá/tên/nhà phát hành đổi ➔ phiên bản mới); dim/bridge nhỏ FULL; fact INCREMENTAL_BY_TIME_RANGE (CCU theo giờ, còn lại theo ngày); `fact_game_reviews` INCREMENTAL_BY_UNIQUE_KEY (MERGE theo review_id).
* Khó khăn đã gặp: sqlglot đổi `payload -> <biểu thức>` thành `JSON_EXTRACT_PATH` (không nhận jsonb) ➔ dùng `JSONB_EXTRACT_PATH`; gõ sai tên biến môi trường làm Jinja chèn chữ `None` vào mật khẩu; `create_external_models` gắn `gateway: local` làm gateway docker không thấy bảng raw.
* DAG transform: `task_load_raw >> task_sqlmesh_run`, `max_active_runs=1`.
* Dọn: xóa `load_dimesions.py`, `load_facts.py`, `create_analytical_views.sql`, `migrate_dwh_schema.py`; drop bảng/view cũ trong `public` và 4 bảng rác không thuộc dự án.
* Quy trình: sửa model ➔ `sqlmesh plan dev` ➔ kiểm tra ➔ `sqlmesh plan` (prod). Airflow chỉ `run`, không tự áp dụng thay đổi code.

### 🔹 Bước 6 (16/10/2026): Tập ~2.000 game cho Data Mining (Game Universe)
* Vấn đề: top 50 chỉ có ~63 game, toàn game cực lớn (owners ≥ 15 triệu, 53/67 game có tag Multiplayer trong top 10), danh sách SteamSpy top100 không đổi giữa 2 ngày ➔ không đủ cho Apriori/K-Means.
* Đưa phần thu thập của HUYNH (`feat/02`: `bulk_collect.py`, IStoreBrowseService) vào pipeline chính:
  - `ingestion/universe.py` ➔ `raw.game_universe`: 2.000 game top owners từ SteamSpy `request=all` (2 trang), chụp mỗi tuần, lỗi thì giữ lần trước.
  - `collector.collect_store_browse`: 50 game/request qua `api.steampowered.com` (giá VND, ngày phát hành, ngôn ngữ, category). `collect_batch` thêm `pause` cho API giới hạn tốc độ.
  - DAG `steam_weekly_universe_ingestion` (01:00 UTC thứ Hai): universe ➔ store browse ➔ SteamSpy (1 req/s) ➔ CCU ➔ Reviews (1,5 s/req), chạy lần lượt, ~2 giờ.
* SQLMesh: thêm `stg_storebrowse_games`, `stg_game_universe`, `stg_game_metadata` (gộp appdetails + store browse); `dim_game` lấy bản mới nhất giữa 2 nguồn, SCD2 chỉ theo dõi tên/giá/giảm giá; thể loại lấy từ SteamSpy `genre` (Store browse không có).
* Marts: dashboard (`mart_ccu_hourly_trend`, `mart_executive_overview`) chỉ lấy top 50 của từng ngày; `mart_mining_features` thêm `app_type`, `owners_min/max`, `release_month`, `publisher_prior_games`, `snapshot_count`, `is_in_universe`.
* Lưu ý: `create_external_models` gắn `gateway: local` và ghi thêm bản trùng ➔ sau mỗi lần chạy phải bỏ dòng gateway và bản cũ.

### 🔹 Bước 7 (20/10/2026): Thay SteamSpy bằng bảng xếp hạng chính thức của Steam
* Vấn đề: SteamSpy `top100in2weeks` trả cùng một danh sách và cùng số liệu suốt 15–20/10 (vẫn ghi "Counter-Strike: Global Offensive"), thiếu Dota 2 (hạng 1 thật), Deadlock, AION 2...; không có game bán chạy (vd. Call of Duty: Modern Warfare 4 đứng đầu bán chạy nhờ đặt trước, chưa phát hành).
* Nguồn mới (`ingestion/catalog.py`), mỗi ngày chụp 2 bảng, gộp lại ~76 game để đo CCU mỗi giờ:
  - `most_played`: `ISteamChartsService/GetGamesByConcurrentPlayers` (toàn cầu, top 50).
  - `top_sellers`: Steam Store search `filter=topsellers&category1=998&cc=VN` (chỉ game, khu vực Việt Nam, top 50).
* `raw.game_catalog_daily` thêm cột `chart`, `concurrent_players`, `peak_ccu_today`; khóa chính `(catalog_date, chart, source, game_id)`. Không xóa dòng cũ: 300 dòng SteamSpy giữ nguyên; `stg_game_catalog` chọn 1 nguồn cho mỗi (ngày, bảng): Steam > SteamSpy > carry_over > fallback.
* SQLMesh: `fact_game_ranking_daily` grain thêm `chart`; 3 mart dashboard lọc `chart = 'most_played'`; mart mới `mart_top_sellers`. Kiểm tra trên môi trường dev: 3 mart cũ khớp prod 100% trước khi `plan` prod.
* Metabase + Streamlit: bảng "Bán chạy nhất trên Steam Việt Nam" ở tab Hôm nay; câu tổng CCU lọc `chart = 'most_played'` để không cộng trùng.
* Mining không bị ảnh hưởng (tập ~2.000 game thu thập riêng); khi train nên lọc `is_in_universe`.

---

## 🎯 BƯỚC TIẾP THEO (NEXT ACTION)
1. Giai đoạn 4: Metabase kết nối schema `marts`, dựng question/dashboard; Streamlit Smart Dashboard lấy dữ liệu qua Metabase API.
2. HUYNH: lấy dữ liệu từ `marts.mart_mining_features`, `dw.bridge_game_tag` (`vote_rank`), `dw.bridge_game_genre`, `dw.fact_game_reviews`.
3. Để máy (kèm WARP) chạy liên tục vài ngày trước buổi báo cáo để có đủ CCU theo giờ.
4. ~~Theo dõi SteamSpy `top100in2weeks`~~ ➔ đã thay bằng bảng xếp hạng chính thức của Steam (Bước 7).
5. Cân nhắc phân trang Reviews API (`cursor`, `filter=recent`) nếu cần nhiều review hơn cho NLP.
