MODEL (
  name staging.stg_player_ccu,
  kind VIEW,
  grain (game_id, snapshot_at),
  description 'Mỗi dòng là 1 lần đo số người chơi đồng thời (CCU) của 1 game'
);

SELECT
  appid AS game_id,
  fetched_at AS snapshot_at,
  (fetched_at AT TIME ZONE 'UTC')::DATE AS snapshot_date,
  EXTRACT(HOUR FROM fetched_at AT TIME ZONE 'UTC')::INT AS snapshot_hour,
  (payload -> 'response' ->> 'player_count')::INT AS concurrent_players,
  object_key AS source_object
FROM raw.steam_ccu_json
WHERE (payload -> 'response' ->> 'result')::INT = 1
  AND payload -> 'response' ->> 'player_count' IS NOT NULL
