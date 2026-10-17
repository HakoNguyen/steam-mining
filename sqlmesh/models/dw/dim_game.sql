MODEL (
  name dw.dim_game,
  kind SCD_TYPE_2_BY_COLUMN (
    unique_key game_id,
    columns [game_title, is_free, price_vnd, price_initial_vnd, discount_pct]
  ),
  cron '@daily',
  description 'Game - SCD Type 2: mỗi lần tên/giá/giảm giá đổi sinh 1 phiên bản mới (valid_from, valid_to). Metadata lấy bản mới nhất giữa Store appdetails và Store browse; giá lấy bản mới nhất CÓ giá (appdetails đôi khi không trả price_overview); SteamSpy bổ sung khi Store thiếu',
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
), price AS (
  -- Appdetails đôi khi không có price_overview (giá chỉ nằm trong package_groups) ➔ price_vnd NULL.
  -- Lấy bản mới nhất có giá để giá không bật qua lại giữa 2 nguồn và sinh phiên bản SCD2 giả.
  SELECT DISTINCT ON (game_id)
    game_id, is_free, price_vnd, price_initial_vnd, discount_pct
  FROM staging.stg_game_metadata
  WHERE is_free OR price_vnd IS NOT NULL
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
  COALESCE(pr.is_free, m.is_free) AS is_free,
  pr.price_vnd,
  pr.price_initial_vnd,
  COALESCE(pr.discount_pct, m.discount_pct) AS discount_pct,
  m.release_date,
  COALESCE(m.developer_name, p.developer_name) AS developer_name,
  COALESCE(m.publisher_name, p.publisher_name) AS publisher_name,
  m.num_languages,
  m.is_multiplayer,
  m.is_coop
FROM meta AS m
FULL OUTER JOIN spy AS p ON p.game_id = m.game_id
LEFT JOIN price AS pr ON pr.game_id = COALESCE(m.game_id, p.game_id)
