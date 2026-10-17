# Hướng dẫn cho HUYNH: dữ liệu Mining và kế hoạch AI Copilot

Tài liệu gồm 2 phần:
- **Phần A:** dựng warehouse trên máy bạn, chỉ phần dữ liệu cho Mining (~2.000 game).
- **Phần B:** kế hoạch AI Copilot, chia việc giữa bạn và phía DE.

---

## Phần A. Dựng dữ liệu Mining trên máy bạn

Pipeline mới (nhánh `main`) thay toàn bộ phần thu thập và biến đổi bạn tự viết trên `feat/02`: `bulk_collect.py`, `load_dimesions.py`, `load_facts.py`, `migrate_dwh_schema.py`. Dữ liệu đi theo đường MinIO → `raw.*` → SQLMesh (`staging` → `dw` → `marts`). Bạn chỉ cần bật 2 DAG:

| DAG | Làm gì |
|---|---|
| `steam_weekly_universe_ingestion` | Lấy ~2.000 game nhiều owners nhất từ SteamSpy, rồi thu thập Store browse, SteamSpy, CCU, Reviews cho từng game. Chạy hằng tuần. |
| `transformation_staging_to_warehouse` | Mỗi giờ: nạp file mới vào `raw.*`, rồi chạy `sqlmesh run` |

4 DAG còn lại (catalog, CCU, metadata, reviews) phục vụ dashboard top 50, bạn để tạm dừng.

### Các bước

```powershell
# 1. Lấy code mới
git checkout main; git pull

# 2. Tạo file cấu hình
copy .env.example .env          # điền mật khẩu
# Tạo sqlmesh\.env gồm 3 dòng:
#   POSTGRES_USER=admin
#   POSTGRES_PASSWORD=<mật khẩu>
#   POSTGRES_DB=steam_dwh

# 3. Dựng Docker. Image Airflow tự build, có sẵn SQLMesh trong venv riêng
docker compose up -d --build

# 4. Tạo các bảng raw
Get-Content scripts\create_dwh_schema.sql | docker exec -i steam_postgres_dwh psql -U admin -d steam_dwh

# 5. Triển khai SQLMesh lần đầu (tạo schema staging / dw / marts)
docker exec -w /opt/airflow/sqlmesh steam_apache_airflow /opt/sqlmesh-venv/bin/sqlmesh --gateway docker plan --auto-apply
```

**6. Trên Airflow UI** (`http://localhost:8080`, tài khoản `admin`/`admin`):
- Bật `transformation_staging_to_warehouse`.
- Bật `steam_weekly_universe_ingestion` và **không bấm chạy tay**. Khi vừa được bật, DAG tự tạo một lượt chạy. Bấm thêm sẽ thành crawl 2 lần.

**7. Bật VPN hoặc Cloudflare WARP trước khi crawl.** Một số nhà mạng chặn `*.steampowered.com`, nên không có VPN thì phần lớn request sẽ lỗi. Crawl mất khoảng 2,5–3 giờ.

**8. Sau 07:00 sáng hôm sau (giờ VN),** dữ liệu đủ trong `marts`. Các bảng theo ngày chỉ tổng hợp khi ngày UTC đã kết thúc. Nếu máy tắt qua đêm, lần transform đầu tiên khi bật máy sẽ tự chạy bù.

### Lấy dữ liệu cho Mining

| Bài toán | Đọc từ |
|---|---|
| Thông tin game, K-Means, CART | `marts.mart_mining_features`, lọc `is_in_universe AND app_type = 'game'` |
| Apriori | `dw.bridge_game_tag` lọc `vote_rank <= 10`, nối `dw.dim_tag` qua `tag_key`; nhãn khen cao: `mart_mining_features.is_high_positive` |
| One-hot thể loại | `dw.bridge_game_genre` nối `dw.dim_genre` qua `genre_key` |
| Phân loại review, chủ đề phàn nàn | `dw.fact_game_reviews` (đã loại trùng; dùng `voted_up`, `review_text`) |

Tên cột thay đổi so với bản cũ của bạn:

| Bản cũ | Bản mới |
|---|---|
| `positive`, `negative` | `positive_reviews`, `negative_reviews` |
| `languages_count` | `num_languages` |
| `has_multiplayer`, `has_coop` | `is_multiplayer`, `is_coop` |
| `release_date_iso` | `release_date` |
| playtime | bỏ, vì SteamSpy luôn trả 0 |

Các cột có sẵn trong `mart_mining_features`:
- `owners_min`, `owners_max`, `owners_mid`, `positive_ratio` (chỉ tính khi có ≥ 50 review)
- `log_owners`, `log_avg_ccu`, `log_price`
- `release_month`, `publisher_prior_games` (cho CART)
- `universe_owners_rank`

**Lưu ý:**
- **Giá:** khoảng 216 game không bán ở vùng VN nên `price_vnd` trống. Khi dùng đặc trưng giá, lọc `price_vnd IS NOT NULL`, nếu không `log_price` sẽ coi các game này là giá 0.
- **Thể loại** lấy từ trường `genre` của SteamSpy, vì Store browse không trả về thể loại.

### Chuyển code Mining sang nhánh mới

Cách gọn nhất là tạo nhánh mới từ `main`, rồi chép sang **chỉ thư mục `mining/`** cùng phần thư viện mining trong `requirements.txt`. Không cần merge `feat/02` nên không phải xử lý xung đột. Cần sửa:
- `prepare_data.py`: 3 hàm đọc dữ liệu đổi sang các bảng ở trên.
- `review_classifier.py` và `negative_topics.py`: đọc `dw.fact_game_reviews` thay vì duyệt file JSON trên MinIO.

---

## Phần B. Kế hoạch AI Copilot

Copilot nằm trong ứng dụng Streamlit (port 8501) và phục vụ 2 nhóm người dùng:

| Trang | Người dùng | Copilot làm gì |
|---|---|---|
| **Smart Dashboard** (DE làm trang) | Hội đồng, nhà phân tích | (1) Phân tích biểu đồ, (2) Bản tin thị trường |
| **Copilot** (bạn làm trang) | Nhà phát hành game nhỏ, người chơi | (3) Trợ lý khảo sát thị trường: "nên làm game gì, thể loại/tag nào, giá bao nhiêu, đối thủ là ai" |

Nguyên tắc chung:
- **Mọi nhận xét phải dựa trên số liệu thật** trong warehouse.
- **Luôn cho xem bằng chứng:** bảng số, công cụ hay câu SQL đã gọi.
- **Nói rõ hạn chế** khi dữ liệu không đủ.

### (1) Phân tích biểu đồ (trên Smart Dashboard)
- **Đầu vào:** mỗi biểu đồ có nút **"🔍 Phân tích"**. Trang dashboard lấy dữ liệu biểu đồ qua Metabase API (`POST /api/card/{id}/query/json`), rồi gửi **chính bảng dữ liệu đó** cho AI (không gửi ảnh chụp), kèm mô tả biểu đồ: tiêu đề, trục, bộ lọc, đơn vị.
- **Đầu ra:** 3–5 nhận xét (xu hướng, điểm bất thường, so sánh nổi bật) kèm con số cụ thể, cuối cùng 1 câu "nên xem thêm gì".
- **Hỏi tiếp:** có ô "Hỏi thêm về biểu đồ này", là một hội thoại ngắn giữ ngữ cảnh bảng dữ liệu.

### (2) Bản tin thị trường (đầu trang Smart Dashboard)
- **Nội dung:** mỗi ngày 1 bản tin gồm game tăng/giảm CCU mạnh nhất, game vào/rơi khỏi top 50, game giảm giá sâu, thể loại đang lên.
- **Số liệu lấy bằng các câu SQL cố định**, không để AI tự viết SQL. AI chỉ viết lời bình, trả về JSON có cấu trúc (`headline`, danh sách mục, mỗi mục kèm số liệu).
- **Lưu theo ngày** vào bảng `copilot.daily_brief`, để không phải gọi AI mỗi lần mở trang.

### (3) Trợ lý khảo sát thị trường (trang Copilot)
Chat tiếng Việt. AI **gọi các công cụ định nghĩa sẵn** thay vì tự do viết SQL:

| Công cụ | Trả lời câu hỏi kiểu | Đọc từ |
|---|---|---|
| `market_overview(genre?, tag?)` | "Thị trường roguelike thế nào?" | `marts.mart_market_by_tag`, `marts.mart_market_by_genre` |
| `tag_opportunities(...)` | "Combo tag nào được khen nhiều mà ít đối thủ?" | `mining.tag_rules` + `mart_market_by_tag` |
| `price_benchmark(genre/tags)` | "Game indie co-op nên bán giá bao nhiêu?" | `marts.mart_mining_features` |
| `similar_games(tags / tên game)` | "Ý tưởng của tôi giống game nào?", "gợi ý game giống X" | `mart_mining_features`, `dw.bridge_game_tag`, `mining.game_clusters` |
| `cluster_profile(cluster)` | "Phân khúc game trả phí ổn định có đặc điểm gì?" | `mining.game_clusters` |
| `run_readonly_sql(query)` | Dự phòng cho câu hỏi không có công cụ riêng | `marts.*`, `mining.*`, chỉ được SELECT |

- **Khung trả lời:** Đề xuất → Bằng chứng (bảng số) → Rủi ro và hạn chế dữ liệu.
- **Minh bạch:** có expander "Copilot đã tra cứu gì", hiện công cụ, tham số và SQL đã chạy.

### Cấu trúc thư mục

```
dashboard/
├── app.py                      # trang chủ Streamlit
├── pages/
│   ├── 1_Smart_Dashboard.py    # DE: biểu đồ từ Metabase API + nút Phân tích + bản tin
│   └── 2_Copilot.py            # HUYNH: chat trợ lý khảo sát thị trường
├── lib/
│   ├── metabase_client.py      # DE: get_card_data(card_id) -> (DataFrame, chart_meta)
│   └── db.py                   # kết nối Postgres bằng user chỉ-đọc copilot_ro
└── copilot/                    # HUYNH
    ├── llm.py                  # lớp bọc nhà cung cấp AI; đổi Claude/Gemini/OpenAI chỉ sửa file này
    ├── chart_insight.py        # (1)
    ├── brief.py                # (2)
    ├── tools.py                # (3) các công cụ + kiểm tra SQL chỉ-đọc
    └── prompts/                # system prompt + tài liệu schema
```

Mỗi người một trang riêng nên không đụng code nhau, chỉ dùng chung thư mục `lib/`.

### Gợi ý kỹ thuật nếu dùng Claude (đổi nhà cung cấp thì chỉ sửa `llm.py`)
- **Mô hình:** mặc định `claude-opus-5-5`. Muốn tiết kiệm thì có thể thử `claude-sonnet-5-5` hoặc `claude-haiku-5-5` cho chức năng (1) và (2), rồi so chất lượng trước khi chốt. Cách giảm chi phí đầu tiên nên thử là `output_config.effort` (`low` hoặc `medium` cho phân tích biểu đồ và bản tin).
- **Trợ lý (3):** dùng Tool Runner của SDK Python (`@beta_tool` + `client.beta.messages.tool_runner(...)`), không phải tự viết vòng lặp gọi công cụ.
- **Prompt caching:** system prompt (vai trò, tài liệu schema, định nghĩa chỉ số) là phần tĩnh và lớn, nên đặt `cache_control` lên đó.
  - **Không** chèn ngày giờ vào system prompt, vì nội dung đổi là mất cache.
  - Kiểm tra cache hoạt động bằng `usage.cache_read_input_tokens > 0`.
- **Bản tin (2):** dùng structured outputs (`client.messages.parse()` hoặc `output_config.format`) để luôn ra JSON đúng khung.
- **Đọc kết quả:** luôn kiểm tra `stop_reason` (đặc biệt `refusal`) trước khi đọc nội dung, và ghi log `usage` để theo dõi chi phí.

### Phía DE chuẩn bị
1. **User Postgres `copilot_ro`:** chỉ được `SELECT` trên `marts` và `mining`, `statement_timeout = 5s`.
2. **Mart tổng hợp:** `marts.mart_market_by_tag` và `marts.mart_market_by_genre`. Mỗi tag/thể loại có: số game, owners trung vị, tỷ lệ khen trung bình, giá trung vị, CCU trung bình, % game F2P.
3. **Mart cho bản tin:** `marts.mart_daily_movers` gồm thay đổi CCU so với hôm qua, game vào/ra top 50, game giảm giá ≥ 50%.
4. **Mô tả cột** cho các mart, xuất ra thành tài liệu schema dùng trong system prompt.
5. **Hạ tầng Streamlit:** `lib/metabase_client.py`, cùng service `streamlit` trong `docker-compose.yml`.

### Phía HUYNH
1. **Ghi kết quả Mining vào schema `mining`** để Copilot và dashboard đọc được, ví dụ:
   - `mining.game_clusters(game_id, cluster_id, cluster_label)`
   - `mining.tag_rules(antecedents, consequents, support, confidence, lift, is_high_positive)`

   Tên bảng và cột có thể khác, chỉ cần báo lại cho DE.
2. **Làm 3 chức năng** theo thứ tự (1) → (2) → (3).
3. **Viết bộ câu hỏi mẫu** để kiểm thử (mục dưới).

### Lộ trình

| Ngày | DE | HUYNH |
|---|---|---|
| 18–19/10 | `copilot_ro`, 3 mart mới, khung Streamlit + `metabase_client` | Ghi kết quả Mining vào `mining`; `llm.py` + **(1) Phân tích biểu đồ** |
| 20–21/10 | Smart Dashboard trên Metabase API | **(2) Bản tin**; 3 công cụ đầu của (3) |
| 22–23/10 | Tích hợp nút Phân tích + bản tin vào dashboard | Hoàn thiện (3): đủ công cụ, `run_readonly_sql`, khung trả lời |
| 24/10 | Kiểm thử chung | Chạy bộ câu hỏi mẫu, chỉnh prompt |
| 25–27/10 | Báo cáo phần DE + demo | Báo cáo phần Mining + Copilot |

Nếu thiếu thời gian: làm chắc chắn (1) và (2), còn (3) làm bản rút gọn với 3 công cụ đầu.

### Kiểm thử
- **Bộ câu hỏi mẫu:** 15–20 câu tiếng Việt, chia theo người dùng (hội đồng / nhà phát hành nhỏ / người chơi). Mỗi câu viết sẵn đáp án bằng SQL tay để so với con số Copilot đưa ra.
- **Phân tích biểu đồ:** mọi con số trong nhận xét phải có trong bảng dữ liệu của biểu đồ.
- **An toàn:**
  - câu yêu cầu xóa/sửa dữ liệu thì bị chặn;
  - câu ngoài phạm vi game/thị trường thì từ chối lịch sự;
  - dữ liệu không có thì nói rõ là warehouse chưa có.
- **Chi phí:** ghi log token mỗi lần gọi, xác nhận cache hoạt động từ lần gọi thứ 2.

### Hạn chế cần ghi rõ (trong giao diện và báo cáo)
- **Thiên lệch người sống sót:** dữ liệu chỉ gồm top 50 (theo giờ) và ~2.000 game nhiều owners nhất (theo tuần). Gợi ý "nên làm game gì" vì vậy dựa trên **game đã thành công**, không thấy được những game thất bại.
- **Độ chính xác của dữ liệu nguồn:** tag do người chơi gắn sau phát hành; owners của SteamSpy là khoảng ước lượng.
- **Phạm vi:** Copilot không có dữ liệu ngoài warehouse, không tra web.
