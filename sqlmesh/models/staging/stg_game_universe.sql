MODEL (
  name staging.stg_game_universe,
  kind VIEW,
  grain (snapshot_date, game_id),
  description 'Tập ~2.000 game nhiều owners nhất (SteamSpy request=all) theo từng lần chụp hàng tuần; is_latest_snapshot đánh dấu lần mới nhất'
);

SELECT
  snapshot_date,
  owners_rank,
  game_id,
  game_title,
  owners_range,
  source,
  snapshot_date = MAX(snapshot_date) OVER () AS is_latest_snapshot
FROM raw.game_universe
