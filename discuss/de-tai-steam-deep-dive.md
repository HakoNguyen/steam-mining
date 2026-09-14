# Báo Cáo Mô Tả Đề Tài: Kho Dữ Liệu & Phân Tích Thị Trường Game Steam

> **Mục tiêu:** Xây dựng hệ thống **Kho Dữ Liệu (Data Warehouse)** và áp dụng các kỹ thuật **Khai Phá Dữ Liệu (Data Mining)** để phân tích xu hướng người chơi, chiến lược định giá, và bóc tách bài đánh giá của người dùng trên nền tảng Steam, tuân thủ đúng khung đề cương môn học PTIT.

---

## I. ỨNG DỤNG THỰC TẾ: AI SẼ CẦN VÀ CẦN ĐỂ LÀM GÌ?

Khi bảo vệ đồ án, đây là câu trả lời giúp chứng minh tính thực tế của đề tài trước hội đồng:

```
+-----------------------------------------------------------------------------------+
|                           3 ĐỐI TƯỢNG SỬ DỤNG THỰC TẾ                              |
+---------------------------+-----------------------------------+-------------------+
| 1. INDIE GAME DEVELOPERS  | 2. GAME PUBLISHERS & INVESTORS    | 3. PRODUCT & CSKH |
|    (Nhà phát triển game)  |    (Nhà phát hành & Đầu tư)       |    (Đội ngũ Live-Ops)|
+---------------------------+-----------------------------------+-------------------+
| • Định giá mở bán         | • Tối ưu % giảm giá đợt Sale      | • Phân loại lỗi   |
| • Chọn thuộc tính Gameplay| • Đánh giá rủi ro trước khi rót vốn|   cần sửa khẩn cấp|
+---------------------------+-----------------------------------+-------------------+
```

### 1. Đối tượng 1: Nhà Phát Triển Game Độc Lập (Indie Game Developers)
* **Họ là ai?** Các nhóm/studio làm game vừa và nhỏ (2–10 người) ở Việt Nam và thế giới.
* **Họ cần phân tích gì & Quyết định gì (Decision)?**
  * **Định giá sản phẩm khi ra mắt (Pricing Decision):** *"Game 2D Pixel của tôi dài 8 tiếng, nên đặt giá 220k hay 330k VNĐ?"* ➔ OLAP Cube chỉ ra ở mức 330k VNĐ, các game cùng thể loại có tỷ lệ chê "Game quá đắt" cao gấp 3 lần ➔ **Quyết định đặt giá 220k VNĐ để tối ưu lượng người mua**.
  * **Định hướng thiết kế Gameplay (Gameplay Features):** *"Nên làm game Thẻ bài thuần túy hay kết hợp Thẻ bài + Roguelite?"* ➔ Thuật toán Apriori chỉ ra mảng `{Deckbuilder, Roguelite} → {HIGH_RATED}` có Confidence 89% và Lift 1.6 ➔ **Quyết định thiết kế theo hướng kết hợp Roguelite ngay từ đầu**.

### 2. Đối tượng 2: Nhà Phát Hành & Quỹ Đầu Tư Game (Game Publishers & VCs)
* **Họ là ai?** Các công ty bỏ vốn phát hành game (Devolver Digital, Team17...) hoặc Quỹ đầu tư mạo hiểm.
* **Họ cần phân tích gì & Quyết định gì (Decision)?**
  * **Tối ưu Mức giảm giá đợt Steam Sale (Discount Elasticity):** Phân tích đợt Sale qua Event Sale Mode DAG cho thấy mức giảm **35% - 40%** tạo độ vọt người chơi (Player Spike) gấp 4.2 lần mức 20% ➔ **Quyết định chốt mức giảm 35%**.
  * **Đánh giá rủi ro rót vốn (Publishing Risk Evaluation):** Quét thông số đối thủ bằng K-Means Clustering (đã chuẩn hóa Log1p + StandardScaler) ➔ **Quyết định có duyệt hợp đồng phát hành hay không**.

### 3. Đối tượng 3: Đội Ngũ Vận Hành & CSKH (Product Managers & Live-Ops Team)
* **Họ là ai?** Đội ngũ phát triển và quản trị cộng đồng sau khi game ra mắt.
* **Họ cần phân tích gì & Quyết định gì (Decision)?**
  * **Xác định ưu tiên sửa lỗi khẩn cấp (Fixing Priority):** Phân loại review 1-sao bằng **BERTopic** chỉ ra 72% phàn nàn về lỗi "Anti-cheat sụt FPS" (Topic 0) ➔ **Quyết định điều động 100% dev dồn sức sửa lỗi Anti-cheat trong đêm**.

---

## II. ĐỐI CHIẾU KHUNG NỘI DUNG ĐỀ CƯƠNG MÔN HỌC (PTIT)

Đề tài được thiết kế bám sát các chương trong đề cương môn Kho Dữ Liệu và Kỹ Thuật Khai Phá:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
|                          ĐỐI CHIẾU NỘI DUNG NỘP ĐỒ ÁN                                  |
|                                                                                        |
|  [ CHƯƠNG 2: TÍCH HỢP DỮ LIỆU ] ➔ Đồng bộ 4 nguồn API. Xử lý xung đột ngữ nghĩa       |
|                                     và lệch đơn vị tiền tệ / số liệu review.           |
|                                                                                        |
|  [ CHƯƠNG 3: KHO DỮ LIỆU & OLAP ] ➔ Dựng Dual-Grain Fact (Snapshot & Aggregate Daily).  |
|                                     Viết SQL ROLLUP/CUBE, thực hiện 5 phép OLAP.       |
|                                                                                        |
|  [ CHƯƠNG 4: KHAI PHÁ DỮ LIỆU ] ➔ • Luật Apriori & FP-Growth (N=10 + HIGH_RATED).      |
|                                     • Phân cụm K-Means (Log1p + StandardScaler).       |
|                                     • Cây quyết định CART (Không rò rỉ dữ liệu).      |
|                                     • Phân loại Text Naive Bayes (GroupStratified).    |
|                                     • Đánh giá mô hình: Confusion Matrix, F1, Recall.  |
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Chương 2: Tích Hợp Dữ Liệu (Data Integration)
* **Xử lý đa nguồn & Xung đột Ngữ nghĩa (Semantic Conflicts):**
  * *Xung đột độ tươi số review:* So sánh `positive/negative` từ SteamSpy (cache trễ) vs Steam Web Reviews API (`query_summary.total_reviews` tươi hơn). **Quy tắc:** Ưu tiên Steam Web Reviews API.
  * *Xung đột Đơn vị & Tiền tệ:* SteamSpy trả USD cent ($1999), Steam Store API trả VND cent (48.000.000). Quy đổi về cùng đơn vị VNĐ.
* **Nguyên tắc ELT & No Time-Travel Bias:**
  * Dữ liệu thô từ Kaggle/SteamSpy dump chỉ lấy thuộc tính bất biến (`title`, `release_date`, `developer`, `publisher`, `original_price`, `genres`, `tags`).
  * Mọi chỉ số biến động (`ccu`, `positive_reviews`, `negative_reviews`, `price_vnd`) lấy 100% từ Pipeline thời gian thực.

### 2. Chương 3: Kho Dữ Liệu & Phân Tích OLAP (Data Warehouse & OLAP)
* **Kiến trúc Dual-Grain Fact:**
  * `fact_player_snapshot`: Grain 1 snapshot / mốc đo (phục vụ Realtime Trend cho Top 300 game).
  * `fact_daily_game_performance`: Grain 1 game / 1 ngày (phục vụ OLAP, Metabase, K-Means & CART Tree).
* **Thực thi 5 phép toán OLAP:**
  * **Pivot 1 (Trục 24h):** `Pivot(hour_utc x genre)` — So sánh đường cong CCU 24 giờ của Singleplayer vs Multiplayer Co-op.
  * **Pivot 2 (Trục Cuối tuần):** `Pivot(day_of_week x tier_code)` — Phân tích chỉ số vọt người chơi cuối tuần (Weekend Spike Ratio).
  * **Slice / Dice:** `Slice(is_free = FALSE)` & `Dice(primary_genre IN ('RPG', 'Strategy') AND price_vnd > 100000)`.
  * **Roll-up / Drill-down:** `Rollup(year -> quarter -> month)` xu hướng phát hành game mới.
  * **Pivot 3 (Mở rộng Sale):** `Pivot(is_sale_period x discount_pct)` phân tích độ co giãn đợt sale.

### 3. Chương 4: Khai Phá Dữ Liệu & Đánh Giá Mô Hình (Data Mining)
* **Luật Kết Hợp (Apriori & FP-Growth):**
  * Khai phá itemset phổ biến từ View `mart_apriori_transactions` ($N=10$, Stop-list trùng Genre đã lọc).
  * Thêm Synthetic Item `HIGH_RATED` (`positive_ratio >= 0.85`) để tạo luật có ý nghĩa hành động.
  * So sánh thời gian thực thi (Execution Time) giữa Apriori và FP-Growth trong `mlxtend`.
* **Phân Cụm Dữ Liệu (Clustering - K-Means):**
  - Tiền xử lý bắt buộc: **`log1p` $\to$ `StandardScaler`** trên 4 feature: `avg_ccu`, `positive_ratio`, `avg_playtime`, `price_vnd`.
  - So sánh kết quả phân cụm Trước vs Sau chuẩn hóa (kèm biểu đồ Silhouette).
  - Chọn $k$ bằng Elbow Method + Silhouette Analysis rồi mới gán tên cụm thực tế.
* **Cây Quyết Định (Classification - CART Tree):**
  - Huấn luyện trên **Game Trả Phí** (`is_free = FALSE`), loại bỏ game rác (`snapshot_count >= 4`).
  - Nhãn: `is_top_performer = 1` nếu `avg_ccu` trong Top 25% của `primary_genre`.
  - Feature set (Không rò rỉ dữ liệu): `release_year`, `publisher_prior_games`, `supported_languages_count`, `has_multiplayer`, `has_coop`, Top-30 Tag One-Hots.
  - Sử dụng thuật toán CART (`criterion='entropy'` / `'gini'`), đánh giá bằng Precision, Recall, F1-Score per class và Stratified K-Fold.
* **Phân Loại Văn Bản (Naive Bayes Text Sentiment):**
  - MultinomialNB trên mảng TF-IDF từ `review_text` $\to$ Dự đoán nhãn `voted_up`.
  - Tách Train/Test bằng **GroupStratified theo `game_id`** (chống rò rỉ review cùng game sang cả 2 tập).
* **Gom Nhóm Chủ Đề (Topic Modeling - BERTopic):** Trích xuất nhóm phàn nàn chính từ review 1-sao.

---

## III. TỔNG KẾT PHẠM VI TRIỂN KHAI

Hệ thống được thiết kế chân thực, chính xác, không đưa ra các dự báo thiếu căn cứ, tập trung vào làm tốt 3 trụ cột môn học: **ETL/ELTL Pipeline ổn định**, **Kho dữ liệu OLAP chuẩn mực**, và **Các mô hình Khai phá dữ liệu được đánh giá đầy đủ chỉ số**.

---

## IV. GIẢ ĐỊNH CHƯA KIỂM CHỨNG (UNVERIFIED ASSUMPTIONS)

1. **Khả năng trả về Tag của SteamSpy:** Cần chạy script audit thực tế xác minh % game trong 5.000 game có dict `tags` hợp lệ vs mảng rỗng `[]`.
2. **Rate Limit 1 req/s của SteamSpy:** Cần test tải thực tế khi chạy DAG Weekly.
3. **Mệnh giá tiền tệ VNĐ trong Store API:** Cần kiểm tra định dạng cents ($\times 100$) trên mẫu dữ liệu thực tế.
4. **Phân bố Modulo `game_id % 24`:** Cần kiểm định độ lệch giữa các bucket `appid` thô.
5. **Nguồn chuẩn cho `dim_game.total_reviews`:** Ưu tiên Steam Web Reviews API (`query_summary.total_reviews`) hơn SteamSpy.
