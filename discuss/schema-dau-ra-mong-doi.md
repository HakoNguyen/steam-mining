# Mô Tả Schema Cấu Trúc Đầu Ra Mong Đợi (Expected Schema Blueprint)

> **Lưu ý:** Tài liệu này **chỉ định nghĩa cấu trúc bảng, kiểu dữ liệu, các trường thuộc tính và định dạng Raw JSON thô** từ các API nguồn. Tài liệu **KHÔNG chứa dữ liệu đầu ra mô phỏng hay con số giả**. Dữ liệu đầu ra thực tế sẽ chỉ được cập nhật sau khi Pipeline ETL chạy thành công trên Database thực tế.

---

## I. CẤU TRÚC DỮ LIỆU THÔ TỪ CÁC ENDPOINT API (RAW PAYLOAD SCHEMAS)

### 1. Steam Store AppDetails API (`store.steampowered.com/api/appdetails?appids={id}`)
* **Format:** JSON Dict
* **Trường dữ liệu thô:**
  * `steam_appid` (Integer): ID game trên Steam.
  * `name` (String): Tên game.
  * `type` (String): Loại ứng dụng (`game`, `dlc`, `mod`).
  * `is_free` (Boolean): Cờ miễn phí.
  * `price_overview.final` (Integer): Giá VND cents ($\times 100$).
  * `price_overview.initial` (Integer): Giá gốc chưa giảm VND cents.
  * `price_overview.discount_percent` (Integer): % giảm giá.
  * `release_date.date` (String): Chuỗi ngày phát hành (Parse ISO `YYYY-MM-DD`).
  * `developers` (Array String): Tên các đơn vị phát triển.
  * `publishers` (Array String): Tên các nhà phát hành.
  * `genres` (Array Dict): Danh sách thể loại `[{"id": "1", "description": "Action"}]`.
  * `categories` (Array Dict): Tính năng game `[{"id": 1, "description": "Multi-player"}]`.

### 2. Steam Concurrent Players API (`api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers`)
* **Format:** JSON Dict
* **Trường dữ liệu thô:**
  * `response.player_count` (Integer): Số người chơi online tại thời điểm gọi API.
  * `response.result` (Integer): Trạng thái trả về (1 = Success).

### 3. SteamSpy API (`steamspy.com/api.php?request=appdetails&appid={id}`)
* **Format:** JSON Dict
* **Trường dữ liệu thô:**
  * `appid` (Integer): ID game.
  * `positive` (Integer): Số review tích cực tích lũy (Cached).
  * `negative` (Integer): Số review tiêu cực tích lũy (Cached).
  * `owners` (String Range): Chuỗi khoảng người sở hữu (Ví dụ: `"100,000,000 .. 200,000,000"`).
  * `tags` (Dict Key-Value / Array): Danh sách tag do người dùng bình chọn `{"FPS": 91172, ...}` hoặc `[]`.

### 4. Steam Customer Reviews API (`store.steampowered.com/appreviews/{id}?json=1`)
* **Format:** JSON Dict
* **Trường dữ liệu thô:**
  * `query_summary.total_reviews` (Integer): Tổng số review (Nguồn chính thức cho `total_reviews`).
  * `reviews` (Array Dict): Danh sách bài nhận xét:
    * `recommendationid` (String): ID duy nhất của review.
    * `review` (String): Nội dung văn bản nhận xét.
    * `voted_up` (Boolean): Nhãn thích (`true`) / không thích (`false`).
    * `timestamp_created` (Integer Unix): Thời điểm viết review.

---

## II. DANH SÁCH BẢNG & TRƯỜNG DỮ LIỆU TRONG KHO DỮ LIỆU (STAR SCHEMA DDL)

### 1. Bảng Chiều Game (`dim_game`)
* `game_id` (INT, Primary Key): ID game.
* `game_title` (VARCHAR(255)): Tên game.
* `app_type` (VARCHAR(20)): Loại ứng dụng (`game`, `dlc`).
* `release_date_iso` (DATE): Ngày phát hành chuẩn ISO.
* `is_free` (BOOLEAN): Cờ game miễn phí.
* `price_vnd` (NUMERIC(12,2)): Giá hiện tại (VNĐ).
* `publisher_name` (VARCHAR(255)): Nhà phát hành chính.
* `developer_name` (VARCHAR(255)): Nhà phát triển chính.
* `primary_genre` (VARCHAR(50)): Thể loại chính (Căn cứ phân Top 25%).
* `total_reviews` (INT): Tổng số review tích lũy.
* `tier_code` (VARCHAR(10)): Tầng phân loại crawl (`TOP_300`, `MID_2000`, `TAIL_3000`, `UNTIERED`).
* `sample_hour` (SMALLINT): Giờ rải mẫu (0-23).

### 2. Bảng Chiều Tag & Bridge Tag (`dim_tag`, `bridge_game_tag`)
* `dim_tag.tag_id` (SERIAL, Primary Key): ID tag.
* `dim_tag.tag_name` (VARCHAR(100)): Tên tag.
* `dim_tag.is_genre_overlap` (BOOLEAN): Cờ đánh dấu tag trùng với Genre cơ bản.
* `bridge_game_tag.game_id` (INT, FK): Trỏ về `dim_game`.
* `bridge_game_tag.tag_id` (INT, FK): Trỏ về `dim_tag`.
* `bridge_game_tag.vote_count` (INT): Số vote của tag cho game đó.
* `bridge_game_tag.vote_share` (NUMERIC(5,4)): Tỷ lệ vote / tổng vote.

### 3. Bảng Chiều Thời Gian (`dim_date`, `dim_time`)
* `dim_date.date_key` (INT, Primary Key): `YYYYMMDD`.
* `dim_date.full_date` (DATE): Ngày đầy đủ.
* `dim_date.day_of_week` (INT): 1 (Thứ 2) đến 7 (Chủ Nhật).
* `dim_date.is_weekend` (BOOLEAN): Cờ cuối tuần.
* `dim_date.is_sale_period` (BOOLEAN): Cờ thuộc đợt Steam Sale.
* `dim_date.sale_event_name` (VARCHAR(50)): Tên đợt sale.
* `dim_time.time_key` (INT, Primary Key): `HHMM`.
* `dim_time.hour_utc` (INT): Giờ UTC (0-23).

### 4. Bảng Sự Kiện Snapshot (`fact_player_snapshot`) — Hourly Grain
* `game_id` (INT, FK), `date_key` (INT, FK), `time_key` (INT, FK).
* `snapshot_timestamp` (TIMESTAMP WITH TIME ZONE).
* `concurrent_players` (INT): Số người chơi online tại thời điểm snapshot.
* `price_vnd` (NUMERIC(12,2)), `discount_percent` (INT).
* `positive_reviews` (BIGINT), `negative_reviews` (BIGINT) (Semi-Additive).
* `owners_min` (BIGINT), `owners_max` (BIGINT).

### 5. Bảng Sự Kiện Tổng Hợp Ngày (`fact_daily_game_performance`) — Daily Grain
* `date_key` (INT, FK), `game_id` (INT, FK).
* `tier_code` (VARCHAR(10)): Tầng lấy mẫu tại thời điểm đó.
* `peak_ccu` (INT): Đỉnh CCU trong ngày.
* `avg_ccu` (NUMERIC(12,2)): CCU trung bình trong ngày.
* `min_ccu` (INT): Đáy CCU trong ngày.
* `snapshot_count` (SMALLINT): Số lượng snapshot thu thập được (24, 4, 1).
* `fetch_error_count` (SMALLINT): Số lần fetch lỗi / 429.
* `price_vnd` (NUMERIC(12,2)), `discount_pct` (SMALLINT).
* `price_as_of_date` (DATE, Nullable): Ngày cập nhật giá gần nhất.

---

## III. GIẢ ĐỊNH CHƯA KIỂM CHỨNG (UNVERIFIED ASSUMPTIONS)

1. **Kiểm chứng dạng dữ liệu Tag từ SteamSpy:** Xác minh độ phủ dữ liệu tag trên mẫu 5.000 game (xử lý cả dict `tags` và mảng rỗng `[]`).
2. **Kiểm chứng Rate Limit SteamSpy:** Kiểm tra thực tế giới hạn 1 req/s trong môi trường Airflow DAG.
3. **Định dạng tiền tệ VNĐ:** Xác nhận công thức `final / 100` cho tất cả game niêm yết tại thị trường Việt Nam.
4. **Phân bố Modulo `game_id % 24`:** Kiểm tra độ lệch tải trên tập `appid` thực tế.
5. **Nguồn chuẩn `total_reviews`:** Sử dụng Steam Web Reviews API làm nguồn chính (`query_summary.total_reviews`) và SteamSpy làm nguồn phụ.
