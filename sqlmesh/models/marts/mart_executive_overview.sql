MODEL (
  name marts.mart_executive_overview,
  kind VIEW,
  description 'Tổng quan top 50 nhiều người chơi nhất (bảng most_played) của ngày gần nhất đã đủ dữ liệu: thứ hạng, CCU, giá, thể loại'
);

WITH latest AS (
  SELECT MAX(full_date) AS full_date FROM dw.fact_daily_game_performance
), genres AS (
  SELECT b.game_id, STRING_AGG(dg.genre_name, ', ' ORDER BY dg.genre_name) AS genres
  FROM dw.bridge_game_genre AS b
  JOIN dw.dim_genre AS dg ON dg.genre_key = b.genre_key
  GROUP BY b.game_id
)
SELECT
  p.full_date,
  c.ranking_order,
  p.game_id,
  g.game_title,
  ge.genres,
  g.is_free,
  g.price_vnd,
  g.discount_pct,
  p.peak_ccu,
  p.avg_ccu
FROM dw.fact_daily_game_performance AS p
JOIN latest ON latest.full_date = p.full_date
JOIN staging.stg_game_catalog AS c
  ON c.game_id = p.game_id AND c.catalog_date = p.full_date AND c.chart = 'most_played'
JOIN dw.dim_game AS g ON g.game_id = p.game_id AND g.valid_to IS NULL
LEFT JOIN genres AS ge ON ge.game_id = p.game_id
