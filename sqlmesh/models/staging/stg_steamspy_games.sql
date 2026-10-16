MODEL (
  name staging.stg_steamspy_games,
  kind VIEW,
  grain (game_id, fetched_at),
  description 'SteamSpy appdetails: tách khoảng owners, số review khen/chê, tỷ lệ khen'
);

WITH base AS (
  SELECT
    appid AS game_id,
    fetched_at,
    (fetched_at AT TIME ZONE 'UTC')::DATE AS fetch_date,
    payload ->> 'name' AS game_title,
    NULLIF(payload ->> 'developer', '') AS developer_name,
    NULLIF(payload ->> 'publisher', '') AS publisher_name,
    NULLIF(REPLACE(SPLIT_PART(payload ->> 'owners', ' .. ', 1), ',', ''), '')::BIGINT AS owners_min,
    NULLIF(REPLACE(SPLIT_PART(payload ->> 'owners', ' .. ', 2), ',', ''), '')::BIGINT AS owners_max,
    (payload ->> 'positive')::INT AS positive_reviews,
    (payload ->> 'negative')::INT AS negative_reviews
  FROM raw.steam_steamspy_json
  WHERE payload ->> 'positive' IS NOT NULL
)
SELECT
  game_id,
  fetched_at,
  fetch_date,
  game_title,
  developer_name,
  publisher_name,
  owners_min,
  owners_max,
  (owners_min + owners_max) / 2 AS owners_mid,
  positive_reviews,
  negative_reviews,
  positive_reviews + negative_reviews AS total_reviews,
  ROUND(positive_reviews::NUMERIC / NULLIF(positive_reviews + negative_reviews, 0), 4) AS positive_ratio
FROM base
