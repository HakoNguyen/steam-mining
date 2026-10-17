MODEL (
  name staging.stg_game_metadata,
  kind VIEW,
  grain (game_id, fetched_at, source),
  description 'Gộp metadata Store từ 2 nguồn về cùng cấu trúc: appdetails (top 50, mỗi ngày) và IStoreBrowseService (~2.000 game, mỗi tuần)'
);

SELECT
  game_id, fetched_at, game_title, app_type, is_free, price_vnd, price_initial_vnd, discount_pct,
  release_date, developer_name, publisher_name, num_languages, is_multiplayer, is_coop,
  'store_appdetails' AS source
FROM staging.stg_store_games

UNION ALL

SELECT
  game_id, fetched_at, game_title, app_type, is_free, price_vnd, price_initial_vnd, discount_pct,
  release_date, developer_name, publisher_name, num_languages, is_multiplayer, is_coop,
  'store_browse' AS source
FROM staging.stg_storebrowse_games
