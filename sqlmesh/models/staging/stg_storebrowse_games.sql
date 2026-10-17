MODEL (
  name staging.stg_storebrowse_games,
  kind VIEW,
  grain (game_id, fetched_at),
  description 'Store metadata qua IStoreBrowseService (mỗi file 1 batch 50 game, dùng cho tập ~2.000 game): tách 1 dòng/game, giá VND, ngày phát hành, số ngôn ngữ, multiplayer/co-op'
);

WITH items AS (
  SELECT
    r.fetched_at,
    it.item
  FROM raw.steam_storebrowse_json AS r
  CROSS JOIN LATERAL JSONB_ARRAY_ELEMENTS(r.payload -> 'response' -> 'store_items') AS it(item)
  WHERE (it.item ->> 'success')::INT = 1
), fields AS (
  SELECT
    fetched_at,
    item,
    COALESCE((item ->> 'is_free')::BOOLEAN, FALSE) AS is_free,
    item -> 'best_purchase_option' AS po,
    (item -> 'release' ->> 'steam_release_date')::BIGINT AS release_ts
  FROM items
)
SELECT
  (item ->> 'appid')::INT AS game_id,
  fetched_at,
  (fetched_at AT TIME ZONE 'UTC')::DATE AS fetch_date,
  item ->> 'name' AS game_title,
  CASE (item ->> 'type')::INT
    WHEN 0 THEN 'game' WHEN 1 THEN 'demo' WHEN 2 THEN 'mod' WHEN 4 THEN 'dlc' WHEN 6 THEN 'software'
    ELSE item ->> 'type'
  END AS app_type,
  is_free,
  CASE WHEN is_free THEN 0 ELSE (po ->> 'final_price_in_cents')::NUMERIC / 100 END AS price_vnd,
  CASE WHEN is_free THEN 0
       ELSE COALESCE(po ->> 'original_price_in_cents', po ->> 'final_price_in_cents')::NUMERIC / 100
  END AS price_initial_vnd,
  COALESCE((po ->> 'discount_pct')::INT, 0) AS discount_pct,
  CASE WHEN release_ts > 0 THEN (TO_TIMESTAMP(release_ts) AT TIME ZONE 'UTC')::DATE END AS release_date,
  (SELECT STRING_AGG(d.dev ->> 'name', ', ') FROM JSONB_ARRAY_ELEMENTS(item -> 'basic_info' -> 'developers') AS d(dev)) AS developer_name,
  (SELECT STRING_AGG(p.pub ->> 'name', ', ') FROM JSONB_ARRAY_ELEMENTS(item -> 'basic_info' -> 'publishers') AS p(pub)) AS publisher_name,
  (SELECT COUNT(*) FROM JSONB_ARRAY_ELEMENTS(item -> 'supported_languages') AS l(lang)
   WHERE (l.lang ->> 'supported')::BOOLEAN)::INT AS num_languages,
  EXISTS (SELECT 1 FROM JSONB_ARRAY_ELEMENTS_TEXT(item -> 'categories' -> 'supported_player_categoryids') AS c(cat_id)
          WHERE c.cat_id::INT IN (1, 24, 36, 37, 47, 49)) AS is_multiplayer,
  EXISTS (SELECT 1 FROM JSONB_ARRAY_ELEMENTS_TEXT(item -> 'categories' -> 'supported_player_categoryids') AS c(cat_id)
          WHERE c.cat_id::INT IN (9, 38, 39, 48)) AS is_coop,
  (item -> 'reviews' -> 'summary_filtered' ->> 'percent_positive')::INT AS store_review_percent_positive,
  (item -> 'reviews' -> 'summary_filtered' ->> 'review_count')::INT AS store_review_count
FROM fields
