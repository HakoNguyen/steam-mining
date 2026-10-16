MODEL (
  name dw.fact_game_daily_stats,
  kind INCREMENTAL_BY_TIME_RANGE (time_column full_date),
  cron '@daily',
  grain (game_id, full_date),
  description 'Owners và số review khen/chê của mỗi game theo ngày (SteamSpy); bản lấy cuối cùng trong ngày',
  audits (unique_combination_of_columns(columns := (game_id, full_date)))
);

SELECT DISTINCT ON (game_id, fetch_date)
  game_id,
  fetch_date AS full_date,
  TO_CHAR(fetch_date, 'YYYYMMDD')::INT AS date_key,
  owners_min,
  owners_max,
  owners_mid,
  positive_reviews,
  negative_reviews,
  total_reviews,
  positive_ratio
FROM staging.stg_steamspy_games
WHERE fetch_date BETWEEN @start_ds AND @end_ds
ORDER BY game_id, fetch_date, fetched_at DESC
