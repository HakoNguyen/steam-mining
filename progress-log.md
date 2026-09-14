# 📝 NHẬT KÝ TIẾN ĐỘ & LỊCH SỬ THẢO LUẬN DỰ ÁN (STEAM DWH & DATA MINING)

> **Mục đích:** Lưu trữ toàn bộ tiến độ công việc, quyết định kỹ thuật, thông số hệ thống và roadmap từng bước để đảm bảo không bị mất dấu ngữ cảnh khi làm việc.

---

## 📌 1. THÔNG TIN DỰ ÁN & THÔNG SỐ HỆ THỐNG

* **Tên đề tài:** Xây dựng kho dữ liệu và khai phá dữ liệu thị trường game trên nền tảng Steam
* **GitHub Repository:** `https://github.com/HakoNguyen/steam-mining.git`
* **Nhánh làm việc chính:** `feat/01` (đã sync với `main`)

### 🌐 Thông số Docker Containers & Cổng truy cập (Local):
* 🗄️ **PostgreSQL 16 (DWH):** `localhost:5432` | DB main: `steam_dwh` | DB phụ: `airflow_db`, `metabase_db` (User: `admin` / Pass: `adminpassword123`)
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

[/] Phase 2: Khởi tạo Schema & Data Lake Storage (ĐANG THỰC HIỆN)
    ├── [x] Tạo Bucket 'raw-steam-data' trên MinIO Console (port 9001)
    └── [ ] Viết DDL Star Schema scripts/create_dwh_schema.sql (Raw JSONB, Dimensions, Facts, Bridge)

[ ] Phase 3: Module Ingestion & Airflow DAGs
    ├── Nâng cấp collector.py (bypass TLS với curl_cffi, retry logic, rate limit)
    └── Viết 3 Airflow DAGs (Hourly CCU, Weekly Metadata, Daily Reviews) đẩy JSON thô vào MinIO S3

[ ] Phase 4: Transformation & ELT Pipeline (Raw ➔ DWH)
    ├── Nạp JSONB từ MinIO vào schema raw trong Postgres
    └── Transform dữ liệu bóc tách nạp vào dim_game, dim_tag, dim_genre, bridge_* và fact_*

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

---

## 🎯 BƯỚC TIẾP THEO (NEXT ACTION)
1. Hoàn thành file [scripts/create_dwh_schema.sql](file:///d:/DE/projects/DWH-DM/scripts/create_dwh_schema.sql) cho DWH Star Schema.
2. Thực thi script DDL vào Postgres `steam_dwh` database.
