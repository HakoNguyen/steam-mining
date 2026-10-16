MODEL (
  name staging.stg_game_genres,
  kind VIEW,
  grain (game_id, genre_name),
  description 'Mỗi dòng là 1 cặp game - thể loại, lấy từ bản Store mới nhất của game'
);

WITH latest AS (
  SELECT DISTINCT ON (appid)
    appid,
    JSONB_EXTRACT_PATH(payload, CAST(appid AS TEXT), 'data') AS d
  FROM raw.steam_store_json
  WHERE JSONB_EXTRACT_PATH_TEXT(payload, CAST(appid AS TEXT), 'success') = 'true'
  ORDER BY appid, fetched_at DESC
)
SELECT DISTINCT
  latest.appid AS game_id,
  TRIM(g.genre ->> 'description') AS genre_name
FROM latest
CROSS JOIN LATERAL JSONB_ARRAY_ELEMENTS(latest.d -> 'genres') AS g(genre)
WHERE TRIM(g.genre ->> 'description') <> ''
