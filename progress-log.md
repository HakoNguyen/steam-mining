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

[/] Phase 4: Transformation & ELT Pipeline (Raw ➔ DWH) — đang chuẩn hóa sang SQLMesh
    ├── [x] Bản tạm bằng Python: transformation/load_dimesions.py, load_facts.py (MinIO ➔ Star Schema)
    ├── [x] (15/10) Nạp JSONB từ MinIO vào schema raw (incremental theo partition ngày + watermark, gồm reviews)
    └── [ ] Chuyển transformation sang SQLMesh (staging ➔ core ➔ marts + audits)

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

---

## 🎯 BƯỚC TIẾP THEO (NEXT ACTION)
1. Giai đoạn 3: cài SQLMesh vào image Airflow, viết models staging ➔ core ➔ marts đọc từ `raw.*` (thay loader Python).
2. Cân nhắc phân trang Reviews API (`cursor`, `filter=recent`) nếu cần nhiều review hơn cho NLP.
