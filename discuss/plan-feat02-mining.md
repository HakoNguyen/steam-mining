# Plan nhánh `feat/02` — Phase 6: Khai phá dữ liệu (issue #8)

Người làm: Hoàng Văn Huynh · Nhánh: `feat/02` (push `feat/02`, KHÔNG push `main`) · Lập ngày 12/10/2026

Nguồn yêu cầu: issue [#8](https://github.com/HakoNguyen/steam-mining/issues/8) + câu hỏi 6–9 trong `discuss/de-xuat-de-tai-steam-dwh.md`.

## Hiện trạng lúc lập plan

- `feat/02` = `feat/01` = `7311172` (ELT của Hiếu, chưa merge `main`). Chưa có commit nào của Huynh.
- Máy này **không có container/volume Steam** → DWH trống, phải dựng lại và thu dữ liệu (Phase 0).
- Python 3.10, có scikit-learn 1.7.2; **thiếu mlxtend**. `requirements.txt` chưa có sklearn/mlxtend/matplotlib/joblib.
- DWH thiếu đặc trưng cho mining: không có % positive, playtime, owners, số ngôn ngữ, multiplayer/co-op (loader SteamSpy đọc positive/negative nhưng chỉ lưu tổng `total_reviews`).
- Issue #7 (views + Metabase) đã đóng nhưng không có file SQL nào được push.

## Phase 0 — Môi trường & dữ liệu

1. `copy .env.example .env`; khi chạy script từ host đặt `POSTGRES_HOST=localhost`, `MINIO_ENDPOINT=localhost:9000` (file mẫu đang để tên container).
2. `docker compose up -d postgres-dwh minio-datalake` (chỉ 2 service này là đủ cho mining).
   - Nếu không kéo được `minio/minio:latest` → đổi image sang `quay.io/minio/minio:latest` (lỗi đã gặp ngày 15/09).
3. Tạo schema: chạy `scripts/create_dwh_schema.sql` vào `steam_dwh`, rồi `python scripts/migrate_dwh_schema.py`.
4. Thu dữ liệu: 50–100 game là quá ít cho mining. Thu thêm bằng SteamSpy `request=all&page=0..N` (1.000 game/trang) để lấy danh sách appid; với mỗi appid gọi `appdetails` của SteamSpy (tag) + Store (genres, categories, languages, giá). SteamSpy giới hạn ~1 req/s → 1.000 game ≈ 20–30 phút. Mục tiêu tối thiểu **≥ 1.000 game**.
   - Hỏi Hiếu: máy Hiếu có đang tích lũy dữ liệu không → xin `pg_dump` để có CCU nhiều ngày.
5. Chạy `transformation/load_dimesions.py` rồi `load_facts.py`. Kiểm tra số dòng `dim_game`, `bridge_game_tag`.
6. Thêm `scikit-learn`, `mlxtend`, `matplotlib`, `joblib` vào `requirements.txt`; `pip install -r requirements.txt`.

**✅ Xong 12/10/2026** — kết quả & thay đổi so với kế hoạch:
- [x] `.env` (host = localhost). [x] Postgres :5433 + MinIO :9000. `minio/minio` đã bị gỡ khỏi Docker Hub, `quay.io/minio/minio` trả 401 → dùng `pgsty/minio:latest` (fork drop-in).
- [x] Schema 9 bảng + migration. [x] requirements + pip.
- [x] Thu **2.000 game** (SteamSpy `request=all` trang 0–1, xếp theo owners) bằng `ingestion/bulk_collect.py` (chạy lại an toàn, bỏ qua appid đã có).
  - **Mạng VN chặn `store.steampowered.com` và `steamcommunity.com`** (DNS trả 127.0.0.1, IP thật timeout) → Store `appdetails` và Reviews API không gọi được. Thay `appdetails` bằng `api.steampowered.com/IStoreBrowseService/GetItems` (không bị chặn, 50 app/request, `country_code=VN` → giá VNĐ ×100): ngày phát hành, giá, categories, ngôn ngữ, publisher/developer. Lưu raw ở `storebrowse/`.
  - Review: thu sau khi bật VPN (`python ingestion/bulk_collect.py reviews`).
- [x] Loader: thứ tự dim → fact như DAG (dim_game nay được tạo từ `storebrowse/`). DWH: 1.956 game (`app_type='game'`), 1.916 có SteamSpy, 1.884 có ngày phát hành, 424 tag / 37.520 cặp game–tag, 25 genre / 5.222 cặp, 1.998 snapshot CCU (1 lần đo/game).
- CCU mới có 1 snapshot/game → `avg_ccu` là ảnh chụp 1 thời điểm, chưa phải trung bình nhiều ngày.

## Phase 1 — Bổ sung đặc trưng vào DWH

Migration `scripts/migrate_mining_features.py` (`ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS ...`):

| Cột | Nguồn | Dùng cho |
|---|---|---|
| `positive`, `negative` | SteamSpy | K-Means, luật kết hợp |
| `owners_min`, `owners_max` | SteamSpy `"a .. b"` → 2 số | K-Means, nhãn CART |
| `avg_playtime_forever`, `median_playtime_forever` | SteamSpy (phút) | K-Means |
| `languages_count` | Store `supported_languages` (đếm, bỏ thẻ HTML) | CART |
| `has_multiplayer`, `has_coop` | Store `categories` (id 1 Multi-player, 9 Co-op, 38 Online Co-op…) | CART |

Sửa `transformation/load_dimesions.py` (file của Hiếu → báo trước): `process_steamspy_dimensions` ghi thêm positive/negative/owners/playtime; `process_store_dimensions` ghi languages_count/has_multiplayer/has_coop. Giữ nguyên UPSERT idempotent.

**✅ Xong 12/10/2026**
- [x] 9 cột thêm vào **`scripts/migrate_dwh_schema.py` có sẵn** (không tạo file migration mới; cùng kiểu `ADD COLUMN IF NOT EXISTS`).
- [x] `load_dimesions.py`: thêm `process_storebrowse_dimensions` (nguồn thay appdetails); gom INSERT dim_game vào `upsert_dim_game`, genre vào `upsert_genre`; SteamSpy ghi positive/negative/owners/playtime và **genre dạng chuỗi** ("Action, Indie" → tách vào `dim_genre`, xử lý xung đột chuỗi/mảng); bỏ qua game SteamSpy chưa có trong dim_game (tránh lỗi FK bridge).
- Category: multiplayer = {1, 24, 36, 37, 47, 49}, co-op = {9, 38, 39, 48}. Kết quả: 1.108 game multiplayer, 677 co-op.
- **SteamSpy trả `average_forever = median_forever = 0` cho mọi game** (đã ngừng cung cấp playtime) → playtime không dùng được cho K-Means.
- [x] Test `transformation/test_load_dimensions.py` (parse owners, đếm ngôn ngữ).

## Phase 2 — `mining/prepare_data.py` (Task 6.1)

- `load_games()` → DataFrame từ `dim_game` + `fact_daily_game_performance` (avg/peak CCU trung bình các ngày, kèm `snapshot_count`).
- `load_tag_transactions(top_k=10)` → list tag mỗi game (lấy top 10 tag theo `vote_count` để giảm nhiễu).
- `load_genres()` → one-hot genre.
- Đặc trưng dẫn xuất: `positive_ratio = positive/(positive+negative)`, `owners_mid`, `log1p` cho CCU/owners/playtime (phân bố lệch rất mạnh).
- Thiếu dữ liệu: bỏ game có `positive+negative < 50` khỏi phân tích tỷ lệ (tỷ lệ không tin cậy); playtime 0 coi là thiếu.

**✅ Xong 12/10/2026** — [x] `load_games`, [x] `load_tag_transactions`, [x] `load_genres`, [x] `add_features` (tách riêng để test không cần DB; thêm `release_month`). `python mining/prepare_data.py` in tóm tắt.
- 1.956 game; `positive_ratio` có ở 1.899 game (trung vị 0,87; 37,4% game ≥ 0,9); 1.916 giao dịch tag (9,9 tag/game); 25 genre (Action 1.188, Indie 807, Adventure 746…).

## Phase 3 — `mining/association_rules.py` (Task 6.4, câu hỏi 6)

- `TransactionEncoder` + `fpgrowth` (mlxtend), `min_support` ≈ 0.05 (chỉnh theo số game), `association_rules(metric="lift", min_threshold=1.2)`.
- Câu "tổ hợp nào gắn với đánh giá tích cực cao": thêm item ảo `HIGH_POSITIVE` cho game có `positive_ratio ≥ 0.9` (ngưỡng ghi rõ), lọc luật có hậu tố = `HIGH_POSITIVE`.
- Xuất: `rules.csv` (support, confidence, lift), biểu đồ top 15 luật theo lift.

**✅ Xong 12/10/2026** — `min_support = 0.03` (0.05 chỉ ra 9 luật HIGH_POSITIVE, toàn luật 1 tag), `max_len = 4`, lift ≥ 1.2.
- 1.916 giao dịch → 466 itemset, 1.042 luật tag–tag, **23 luật → HIGH_POSITIVE** (tỷ lệ nền 37,4%).
- Tag–tag: luật lift cao nhất là nhóm đồng nghĩa (FPS ↔ First-Person + Shooter, lift ~6–7) — đúng nhưng hiển nhiên.
- **Câu hỏi 6**: tổ hợp gắn với ≥ 90% review tích cực: Great Soundtrack (conf 0,66, lift 1,76), Great Soundtrack + Singleplayer (1,75), Difficult (1,72), Indie + Singleplayer (1,68), Horror + Singleplayer (1,64), 2D (1,62), Pixel Graphics, Puzzle, Story Rich… → game **đơn, indie, nặng nghệ thuật/cốt truyện** được đánh giá cao hơn hẳn; không có tag multiplayer/F2P nào lọt top.
- Đầu ra: `rules.csv`, `rules_high_positive.csv`, `rules_top15_lift.png`, `rules_high_positive_top15.png`.

## Phase 4 — `mining/kmeans_clustering.py` (Task 6.2, câu hỏi 7)

- Đặc trưng: `log1p(owners_mid hoặc avg_ccu)`, `price_vnd`, `positive_ratio`, `log1p(median_playtime)` → `StandardScaler`.
- Chọn k: chạy k = 2..10, vẽ Elbow (inertia) + Silhouette; chọn k theo silhouette, ghi lý do.
- Đặt tên cụm **sau khi** xem bảng trung bình đặc trưng mỗi cụm (không đặt trước tên "AAA Hits…").
- Xuất: `kmeans.joblib` (kèm scaler), `elbow_silhouette.png`, `clusters_pca.png` (PCA 2D), `cluster_profile.csv`.

## Phase 5 — `mining/cart_tree.py` (Task 6.3, câu hỏi 8)

- Nhãn: game thuộc **top 25% `owners_mid` trong thể loại chính** của nó (theo đề xuất "hiệu suất cao trong thể loại").
- Đặc trưng **chỉ có trước phát hành** (tránh leakage): giá, is_free, languages_count, has_multiplayer, has_coop, số game publisher đã phát hành **trước ngày phát hành của game này**, one-hot top 20 tag, genre, tháng phát hành. KHÔNG dùng CCU, review, owners, playtime.
- `DecisionTreeClassifier(max_depth=4..6, class_weight="balanced")`, chia 80/20 stratified + 5-fold CV; chọn depth bằng CV.
- Đánh giá: Accuracy, Precision, Recall, F1, confusion matrix, so với baseline đoán lớp đa số.
- Xuất: `cart.joblib`, `tree.png` (`plot_tree`), `tree_rules.txt` (`export_text`, luật nếu–thì), `feature_importance.png`, `metrics.json`.

## Phase 6 — Phân loại văn bản review (câu hỏi 9, ngoài issue #8 → hỏi Hiếu ai làm)

- Dữ liệu: JSON `reviews/` trong MinIO (Reviews API, nhãn `voted_up`), khử trùng theo `recommendationid`.
- TF-IDF + LogisticRegression (so với MultinomialNB); lệch lớp → báo F1-macro, không chỉ accuracy.
- Mở rộng (nếu còn thời gian): gom chủ đề review tiêu cực (câu hỏi 10).

## Phase 7 — Đầu ra, kiểm tra, PR

- Tất cả kết quả ghi vào `mining/outputs/` (model `.joblib`, `.png`, `.csv`, `metrics.json`).
- Một file kiểm tra nhỏ `mining/test_mining.py`: chạy 3 mô hình trên dữ liệu giả vài chục dòng, assert không lỗi và đủ file đầu ra.
- Mỗi task một commit, push `feat/02`. Mở PR `feat/02` → `main` cho Hiếu review (không tự merge).
  - Lưu ý: `feat/02` đang chứa 3 commit chưa merge của `feat/01` → nhờ Hiếu merge `feat/01` trước để PR chỉ còn phần mining.

## Thứ tự làm & việc cần hỏi Hiếu

Thứ tự: Phase 0 → 1 → 2 → **3 (luật kết hợp, dữ liệu tag sẵn nhất)** → 4 → 5 → 7 → 6.

Hỏi Hiếu:
1. Xin dump DWH / dữ liệu MinIO đang tích lũy (nếu có).
2. Đồng ý cho sửa `load_dimesions.py` để thêm cột cho mining.
3. Phần phân loại review (câu 9) do ai làm.
4. File views/dashboard của issue #7 đang ở đâu (chưa thấy trên GitHub).
