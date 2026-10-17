MODEL (
  name staging.stg_store_games,
  kind VIEW,
  grain (game_id, fetched_at),
  description 'Store appdetails: tách cột, giá VND, parse ngày phát hành, đếm ngôn ngữ, cờ multiplayer/co-op'
);

WITH base AS (
  SELECT
    appid,
    fetched_at,
    -- Khóa JSON là appid (động) nên dùng hàm thay cho toán tử ->,
    -- vì sqlglot đổi "payload -> <biểu thức>" thành JSON_EXTRACT_PATH (không nhận jsonb)
    JSONB_EXTRACT_PATH(payload, CAST(appid AS TEXT), 'data') AS d
  FROM raw.steam_store_json
  WHERE JSONB_EXTRACT_PATH_TEXT(payload, CAST(appid AS TEXT), 'success') = 'true'
), fields AS (
  SELECT
    appid,
    fetched_at,
    d,
    (d ->> 'is_free')::BOOLEAN AS is_free,
    d -> 'price_overview' AS po,
    (d -> 'release_date' ->> 'date') AS release_raw
  FROM base
)
SELECT
  appid AS game_id,
  fetched_at,
  (fetched_at AT TIME ZONE 'UTC')::DATE AS fetch_date,
  d ->> 'name' AS game_title,
  d ->> 'type' AS app_type,
  is_free,
  (po ->> 'currency') AS currency,
  CASE WHEN is_free THEN 0
       WHEN (po ->> 'currency') = 'VND' THEN (po ->> 'final')::NUMERIC / 100
  END AS price_vnd,
  CASE WHEN is_free THEN 0
       WHEN (po ->> 'currency') = 'VND' THEN (po ->> 'initial')::NUMERIC / 100
  END AS price_initial_vnd,
  COALESCE((po ->> 'discount_percent')::INT, 0) AS discount_pct,
  CASE
    WHEN release_raw ~ '^[0-9]{1,2} [A-Za-z]{3}, [0-9]{4}$' THEN TO_DATE(release_raw, 'DD Mon, YYYY')
    WHEN release_raw ~ '^[A-Za-z]{3} [0-9]{1,2}, [0-9]{4}$' THEN TO_DATE(release_raw, 'Mon DD, YYYY')
  END AS release_date,
  (SELECT STRING_AGG(dev.name, ', ') FROM JSONB_ARRAY_ELEMENTS_TEXT(d -> 'developers') AS dev(name)) AS developer_name,
  (SELECT STRING_AGG(pub.name, ', ') FROM JSONB_ARRAY_ELEMENTS_TEXT(d -> 'publishers') AS pub(name)) AS publisher_name,
  ARRAY_LENGTH(
    STRING_TO_ARRAY(REGEXP_REPLACE(SPLIT_PART(d ->> 'supported_languages', '<br>', 1), '<[^>]+>', '', 'g'), ','),
    1
  ) AS num_languages,
  EXISTS (SELECT 1 FROM JSONB_ARRAY_ELEMENTS(d -> 'categories') AS c(cat)
          WHERE (c.cat ->> 'id')::INT IN (1, 24, 36, 37, 47, 49)) AS is_multiplayer,
  EXISTS (SELECT 1 FROM JSONB_ARRAY_ELEMENTS(d -> 'categories') AS c(cat)
          WHERE (c.cat ->> 'id')::INT IN (9, 38, 39, 48)) AS is_coop
FROM fields
