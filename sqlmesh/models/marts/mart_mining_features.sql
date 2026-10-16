MODEL (
  name marts.mart_mining_features,
  kind VIEW,
  description 'Đặc trưng cho 5 bài Data Mining: mỗi dòng 1 game, đã tính sẵn log1p và nhãn HIGH_POSITIVE'
);

WITH stats AS (
  SELECT DISTINCT ON (game_id)
    game_id, owners_mid, positive_reviews, negative_reviews, total_reviews, positive_ratio
  FROM dw.fact_game_daily_stats
  ORDER BY game_id, full_date DESC
), ccu AS (
  SELECT game_id, ROUND(AVG(avg_ccu), 2) AS avg_ccu, MAX(peak_ccu) AS peak_ccu
  FROM dw.fact_daily_game_performance
  GROUP BY game_id
)
SELECT
  g.game_id,
  g.game_title,
  g.is_free,
  g.price_vnd,
  g.num_languages,
  g.is_multiplayer,
  g.is_coop,
  g.release_date,
  g.developer_name,
  g.publisher_name,
  s.owners_mid,
  s.positive_reviews,
  s.negative_reviews,
  s.total_reviews,
  CASE WHEN s.total_reviews >= 50 THEN s.positive_ratio END AS positive_ratio,
  COALESCE(s.total_reviews >= 50 AND s.positive_ratio >= 0.9, FALSE) AS is_high_positive,
  c.avg_ccu,
  c.peak_ccu,
  LN(COALESCE(s.owners_mid, 0) + 1) AS log_owners,
  LN(COALESCE(c.avg_ccu, 0) + 1) AS log_avg_ccu,
  LN(COALESCE(g.price_vnd, 0) + 1) AS log_price
FROM dw.dim_game AS g
LEFT JOIN stats AS s ON s.game_id = g.game_id
LEFT JOIN ccu AS c ON c.game_id = g.game_id
WHERE g.valid_to IS NULL
