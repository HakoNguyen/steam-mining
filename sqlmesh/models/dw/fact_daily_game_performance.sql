MODEL (
  name dw.fact_daily_game_performance,
  kind INCREMENTAL_BY_TIME_RANGE (time_column full_date),
  cron '@daily',
  grain (game_id, full_date),
  description 'CCU gộp theo ngày (peak/avg/min); giá lấy đúng phiên bản dim_game có hiệu lực trong ngày đó (SCD2)',
  audits (
    not_null(columns := (game_id, full_date, peak_ccu)),
    unique_combination_of_columns(columns := (game_id, full_date))
  )
);

WITH daily AS (
  SELECT
    game_id,
    (snapshot_at AT TIME ZONE 'UTC')::DATE AS full_date,
    MAX(concurrent_players) AS peak_ccu,
    ROUND(AVG(concurrent_players), 2) AS avg_ccu,
    MIN(concurrent_players) AS min_ccu,
    COUNT(*) AS snapshot_count
  FROM dw.fact_player_snapshot
  WHERE snapshot_at BETWEEN @start_tstz AND @end_tstz
  GROUP BY 1, 2
)
SELECT
  d.game_id,
  d.full_date,
  TO_CHAR(d.full_date, 'YYYYMMDD')::INT AS date_key,
  d.peak_ccu,
  d.avg_ccu,
  d.min_ccu,
  d.snapshot_count,
  g.price_vnd,
  g.discount_pct
FROM daily AS d
LEFT JOIN dw.dim_game AS g
  ON g.game_id = d.game_id
 AND d.full_date >= g.valid_from::DATE
 AND (g.valid_to IS NULL OR d.full_date < g.valid_to::DATE)
