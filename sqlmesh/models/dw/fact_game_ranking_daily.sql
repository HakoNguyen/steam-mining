MODEL (
  name dw.fact_game_ranking_daily,
  kind INCREMENTAL_BY_TIME_RANGE (time_column full_date),
  cron '@daily',
  grain (game_id, full_date, chart),
  description 'Thứ hạng của game trong 2 bảng xếp hạng Steam mỗi ngày: most_played (nhiều người chơi nhất) và top_sellers (bán chạy nhất tại Việt Nam)',
  audits (
    not_null(columns := (game_id, full_date, chart, ranking_order)),
    unique_combination_of_columns(columns := (game_id, full_date, chart))
  )
);

SELECT
  game_id,
  catalog_date AS full_date,
  TO_CHAR(catalog_date, 'YYYYMMDD')::INT AS date_key,
  chart,
  ranking_order,
  source
FROM staging.stg_game_catalog
WHERE catalog_date BETWEEN @start_ds AND @end_ds
