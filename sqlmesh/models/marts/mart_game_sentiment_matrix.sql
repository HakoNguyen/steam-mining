MODEL (
  name marts.mart_game_sentiment_matrix,
  kind VIEW,
  description 'Mỗi game: phân khúc giá × mức độ khen'
);

WITH stats AS (
  SELECT DISTINCT ON (game_id) game_id, total_reviews, positive_ratio
  FROM dw.fact_game_daily_stats
  ORDER BY game_id, full_date DESC
)
SELECT
  g.game_id,
  g.game_title,
  g.price_vnd,
  CASE
    WHEN g.is_free THEN 'Free-to-Play'
    WHEN g.price_vnd < 100000 THEN 'Budget (<100k)'
    WHEN g.price_vnd <= 500000 THEN 'Mid-tier (100k-500k)'
    WHEN g.price_vnd > 500000 THEN 'Premium (>500k)'
    ELSE 'Chưa rõ giá'
  END AS price_tier,
  s.total_reviews,
  s.positive_ratio,
  CASE
    WHEN s.total_reviews IS NULL OR s.total_reviews < 50 THEN 'Chưa đủ review'
    WHEN s.positive_ratio >= 0.9 THEN 'Rất tích cực (≥90%)'
    WHEN s.positive_ratio >= 0.7 THEN 'Tích cực (70-90%)'
    WHEN s.positive_ratio >= 0.4 THEN 'Trái chiều (40-70%)'
    ELSE 'Tiêu cực (<40%)'
  END AS sentiment_tier
FROM dw.dim_game AS g
LEFT JOIN stats AS s ON s.game_id = g.game_id
WHERE g.valid_to IS NULL
