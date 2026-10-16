MODEL (
  name dw.dim_game,
  kind SCD_TYPE_2_BY_COLUMN (
    unique_key game_id,
    columns [game_title, is_free, price_vnd, price_initial_vnd, discount_pct]
  ),
  cron '@daily',
  description 'Game - SCD Type 2: mỗi lần tên/giá/giảm giá đổi sinh 1 phiên bản mới (valid_from, valid_to). Metadata lấy bản mới nhất giữa Store appdetails và Store browse; SteamSpy bổ sung khi Store thiếu',
  audits (
    not_null(columns := (game_id, game_title)),
    unique_combination_of_columns(columns := (game_id, valid_from))
  )
);

WITH meta AS (
  SELECT DISTINCT ON (game_id)
    game_id, game_title, app_type, is_free, price_vnd, price_initial_vnd, discount_pct,
    release_date, developer_name, publisher_name, num_languages, is_multiplayer, is_coop
  FROM staging.stg_game_metadata
  ORDER BY game_id, fetched_at DESC
), spy AS (
  SELECT DISTINCT ON (game_id)
    game_id, game_title, developer_name, publisher_name
  FROM staging.stg_steamspy_games
  ORDER BY game_id, fetched_at DESC
)
SELECT
  COALESCE(m.game_id, p.game_id) AS game_id,
  COALESCE(m.game_title, p.game_title) AS game_title,
  m.app_type,
  m.is_free,
  m.price_vnd,
  m.price_initial_vnd,
  m.discount_pct,
  m.release_date,
  COALESCE(m.developer_name, p.developer_name) AS developer_name,
  COALESCE(m.publisher_name, p.publisher_name) AS publisher_name,
  m.num_languages,
  m.is_multiplayer,
  m.is_coop
FROM meta AS m
FULL OUTER JOIN spy AS p ON p.game_id = m.game_id
