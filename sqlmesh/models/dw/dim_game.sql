MODEL (
  name dw.dim_game,
  kind SCD_TYPE_2_BY_COLUMN (
    unique_key game_id,
    columns [game_title, is_free, price_vnd, price_initial_vnd, discount_pct, developer_name, publisher_name]
  ),
  cron '@daily',
  description 'Game - SCD Type 2: mỗi lần giá/tên/nhà phát hành đổi sinh 1 phiên bản mới (valid_from, valid_to)',
  audits (
    not_null(columns := (game_id, game_title)),
    unique_combination_of_columns(columns := (game_id, valid_from))
  )
);

WITH store AS (
  SELECT DISTINCT ON (game_id)
    game_id, game_title, app_type, is_free, price_vnd, price_initial_vnd, discount_pct,
    release_date, developer_name, publisher_name, num_languages, is_multiplayer, is_coop
  FROM staging.stg_store_games
  ORDER BY game_id, fetched_at DESC
), spy AS (
  SELECT DISTINCT ON (game_id)
    game_id, game_title, developer_name, publisher_name
  FROM staging.stg_steamspy_games
  ORDER BY game_id, fetched_at DESC
)
SELECT
  s.game_id,
  COALESCE(s.game_title, p.game_title) AS game_title,
  s.app_type,
  s.is_free,
  s.price_vnd,
  s.price_initial_vnd,
  s.discount_pct,
  s.release_date,
  COALESCE(s.developer_name, p.developer_name) AS developer_name,
  COALESCE(s.publisher_name, p.publisher_name) AS publisher_name,
  s.num_languages,
  s.is_multiplayer,
  s.is_coop
FROM store AS s
LEFT JOIN spy AS p ON p.game_id = s.game_id
