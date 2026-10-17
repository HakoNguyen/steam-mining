MODEL (
  name marts.mart_mining_features,
  kind VIEW,
  description 'Đặc trưng cho Data Mining: mỗi dòng 1 game (tập ~2.000 game và top 50), đã tính sẵn log1p, nhãn HIGH_POSITIVE, số game publisher đã ra trước đó'
);

WITH stats AS (
  SELECT DISTINCT ON (game_id)
    game_id, owners_min, owners_max, owners_mid, positive_reviews, negative_reviews, total_reviews, positive_ratio
  FROM dw.fact_game_daily_stats
  ORDER BY game_id, full_date DESC
), ccu AS (
  SELECT
    game_id,
    ROUND(AVG(avg_ccu), 2) AS avg_ccu,
    MAX(peak_ccu) AS peak_ccu,
    SUM(snapshot_count) AS snapshot_count
  FROM dw.fact_daily_game_performance
  GROUP BY game_id
), universe AS (
  SELECT game_id, owners_rank
  FROM staging.stg_game_universe
  WHERE is_latest_snapshot
)
SELECT
  g.game_id,
  g.game_title,
  g.app_type,
  g.is_free,
  g.price_vnd,
  g.num_languages,
  g.is_multiplayer,
  g.is_coop,
  g.release_date,
  EXTRACT(MONTH FROM g.release_date)::INT AS release_month,
  g.developer_name,
  g.publisher_name,
  COUNT(*) OVER (
    PARTITION BY g.publisher_name
    ORDER BY g.release_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
  ) AS publisher_prior_games,
  s.owners_min,
  s.owners_max,
  s.owners_mid,
  s.positive_reviews,
  s.negative_reviews,
  s.total_reviews,
  CASE WHEN s.total_reviews >= 50 THEN s.positive_ratio END AS positive_ratio,
  COALESCE(s.total_reviews >= 50 AND s.positive_ratio >= 0.9, FALSE) AS is_high_positive,
  c.avg_ccu,
  c.peak_ccu,
  COALESCE(c.snapshot_count, 0) AS snapshot_count,
  u.owners_rank AS universe_owners_rank,
  u.game_id IS NOT NULL AS is_in_universe,
  LN(COALESCE(s.owners_mid, 0) + 1) AS log_owners,
  LN(COALESCE(c.avg_ccu, 0) + 1) AS log_avg_ccu,
  LN(COALESCE(g.price_vnd, 0) + 1) AS log_price
FROM dw.dim_game AS g
LEFT JOIN stats AS s ON s.game_id = g.game_id
LEFT JOIN ccu AS c ON c.game_id = g.game_id
LEFT JOIN universe AS u ON u.game_id = g.game_id
WHERE g.valid_to IS NULL
