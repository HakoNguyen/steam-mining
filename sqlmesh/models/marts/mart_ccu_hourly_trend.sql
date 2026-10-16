MODEL (
  name marts.mart_ccu_hourly_trend,
  kind VIEW,
  description 'CCU từng lần đo, kèm tên game, giờ Việt Nam và buổi trong ngày'
);

SELECT
  f.game_id,
  g.game_title,
  f.snapshot_at,
  f.snapshot_at AT TIME ZONE 'Asia/Ho_Chi_Minh' AS snapshot_at_vn,
  f.date_key,
  t.hour_vn,
  t.day_part_vn,
  f.concurrent_players
FROM dw.fact_player_snapshot AS f
JOIN dw.dim_game AS g ON g.game_id = f.game_id AND g.valid_to IS NULL
JOIN dw.dim_time AS t ON t.time_key = f.time_key
