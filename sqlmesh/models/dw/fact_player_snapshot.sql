MODEL (
  name dw.fact_player_snapshot,
  kind INCREMENTAL_BY_TIME_RANGE (time_column snapshot_at),
  cron '@hourly',
  grain (game_id, snapshot_at),
  description 'Mỗi dòng là 1 lần đo CCU; chỉ append khoảng giờ mới, dữ liệu cũ không bị tính lại',
  audits (
    not_null(columns := (game_id, snapshot_at, concurrent_players)),
    accepted_range(column := concurrent_players, min_v := 0)
  )
);

SELECT
  game_id,
  TO_CHAR(snapshot_date, 'YYYYMMDD')::INT AS date_key,
  snapshot_hour AS time_key,
  snapshot_at,
  concurrent_players,
  source_object
FROM staging.stg_player_ccu
WHERE snapshot_at BETWEEN @start_tstz AND @end_tstz
