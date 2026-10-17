MODEL (
  name dw.fact_game_ranking_daily,
  kind INCREMENTAL_BY_TIME_RANGE (time_column full_date),
  cron '@daily',
  grain (game_id, full_date),
  description 'Thứ hạng của game trong top 50 mỗi ngày và CCU đỉnh hôm trước theo SteamSpy',
  audits (unique_combination_of_columns(columns := (game_id, full_date)))
);

SELECT
  game_id,
  catalog_date AS full_date,
  TO_CHAR(catalog_date, 'YYYYMMDD')::INT AS date_key,
  ranking_order,
  ccu_peak_yesterday
FROM staging.stg_game_catalog
WHERE catalog_date BETWEEN @start_ds AND @end_ds
