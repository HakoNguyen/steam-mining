MODEL (
  name marts.mart_market_by_genre,
  kind VIEW,
  grain genre_name,
  description 'Thị trường theo từng thể loại (tập ~2.000 game): quy mô, mức cạnh tranh, độ được khen, giá, CCU. Dùng cho Copilot khảo sát thị trường',
  column_descriptions (
    genre_name = 'Tên thể loại (SteamSpy genre)',
    n_games = 'Số game thuộc thể loại - càng nhiều càng cạnh tranh',
    median_owners = 'Số người sở hữu trung vị (điểm giữa khoảng owners của SteamSpy; khoảng thô nên ít phân biệt)',
    avg_owners = 'Số người sở hữu trung bình mỗi game - dùng để so sánh quy mô giữa các thể loại',
    avg_positive_ratio = 'Tỷ lệ review khen trung bình (chỉ game có >= 50 review)',
    pct_high_positive = 'Phần trăm game được khen >= 90%',
    median_price_vnd = 'Giá trung vị (VND) của game trả phí có giá',
    pct_free = 'Phần trăm game miễn phí',
    avg_ccu = 'Số người chơi đồng thời trung bình mỗi game',
    median_ccu = 'Số người chơi đồng thời trung vị mỗi game'
  )
);

SELECT
  g.genre_name,
  COUNT(*) AS n_games,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.owners_mid) AS median_owners,
  ROUND(AVG(f.owners_mid)::NUMERIC, 0) AS avg_owners,
  ROUND(AVG(f.positive_ratio)::NUMERIC, 4) AS avg_positive_ratio,
  ROUND(100.0 * AVG(CASE WHEN f.is_high_positive THEN 1 ELSE 0 END), 1) AS pct_high_positive,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.price_vnd) FILTER (WHERE NOT f.is_free AND f.price_vnd > 0) AS median_price_vnd,
  ROUND(100.0 * AVG(CASE WHEN f.is_free THEN 1 ELSE 0 END), 1) AS pct_free,
  ROUND(AVG(f.avg_ccu)::NUMERIC, 0) AS avg_ccu,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.avg_ccu) AS median_ccu
FROM dw.bridge_game_genre AS b
JOIN dw.dim_genre AS g ON g.genre_key = b.genre_key
JOIN marts.mart_mining_features AS f ON f.game_id = b.game_id
WHERE f.is_in_universe AND f.app_type = 'game'
GROUP BY g.genre_name
