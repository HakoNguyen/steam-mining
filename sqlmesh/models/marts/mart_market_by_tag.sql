MODEL (
  name marts.mart_market_by_tag,
  kind VIEW,
  grain tag_name,
  description 'Thị trường theo từng tag (tập ~2.000 game): quy mô, mức cạnh tranh, độ được khen, giá, CCU. Dùng cho Copilot khảo sát thị trường',
  column_descriptions (
    tag_name = 'Tên tag do người chơi gắn (SteamSpy)',
    n_games = 'Số game có tag này - càng nhiều càng cạnh tranh',
    n_games_top10 = 'Số game có tag này nằm trong 10 tag nhiều vote nhất của game (tag đặc trưng)',
    median_owners = 'Số người sở hữu trung vị (điểm giữa khoảng owners của SteamSpy; khoảng thô nên ít phân biệt)',
    avg_owners = 'Số người sở hữu trung bình mỗi game - dùng để so sánh quy mô giữa các tag',
    avg_positive_ratio = 'Tỷ lệ review khen trung bình (chỉ game có >= 50 review)',
    pct_high_positive = 'Phần trăm game được khen >= 90%',
    median_price_vnd = 'Giá trung vị (VND) của game trả phí có giá',
    pct_free = 'Phần trăm game miễn phí',
    avg_ccu = 'Số người chơi đồng thời trung bình mỗi game',
    median_ccu = 'Số người chơi đồng thời trung vị mỗi game'
  )
);

SELECT
  t.tag_name,
  COUNT(*) AS n_games,
  COUNT(*) FILTER (WHERE b.vote_rank <= 10) AS n_games_top10,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.owners_mid) AS median_owners,
  ROUND(AVG(f.owners_mid)::NUMERIC, 0) AS avg_owners,
  ROUND(AVG(f.positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
  ROUND(100.0 * AVG(CASE WHEN f.is_high_positive THEN 1 ELSE 0 END), 1) AS pct_high_positive,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.price_vnd) FILTER (WHERE NOT f.is_free AND f.price_vnd > 0) AS median_price_vnd,
  ROUND(100.0 * AVG(CASE WHEN f.is_free THEN 1 ELSE 0 END), 1) AS pct_free,
  ROUND(AVG(f.avg_ccu)::NUMERIC, 0) AS avg_ccu,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.avg_ccu) AS median_ccu
FROM dw.bridge_game_tag AS b
JOIN dw.dim_tag AS t ON t.tag_key = b.tag_key
JOIN marts.mart_mining_features AS f ON f.game_id = b.game_id
WHERE f.is_in_universe AND f.app_type = 'game'
GROUP BY t.tag_name
