MODEL (
  name marts.mart_ccu_hourly_trend,
  kind VIEW,
  description 'CCU từng lần đo của các game thuộc top 50 nhiều người chơi nhất (bảng most_played) ngày hôm đó, kèm thứ hạng, giờ Việt Nam và buổi trong ngày (tập ~2.000 game Mining đo 1 lần/tuần nên không đưa vào đây)'
);

SELECT
  f.game_id,
  g.game_title,
  c.ranking_order,
  f.snapshot_at,
  f.snapshot_at AT TIME ZONE 'Asia/Ho_Chi_Minh' AS snapshot_at_vn,
  f.date_key,
  t.hour_vn,
  t.day_part_vn,
  f.concurrent_players
FROM dw.fact_player_snapshot AS f
JOIN staging.stg_game_catalog AS c
  ON c.game_id = f.game_id
 AND c.catalog_date = (f.snapshot_at AT TIME ZONE 'UTC')::DATE
 AND c.chart = 'most_played'
JOIN dw.dim_game AS g ON g.game_id = f.game_id AND g.valid_to IS NULL
JOIN dw.dim_time AS t ON t.time_key = f.time_key
