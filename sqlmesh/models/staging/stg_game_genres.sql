MODEL (
  name staging.stg_game_genres,
  kind VIEW,
  grain (game_id, genre_name),
  description 'Mỗi dòng là 1 cặp game - thể loại, tách từ trường genre của bản SteamSpy mới nhất (nguồn duy nhất có thể loại cho cả ~2.000 game)'
);

WITH latest AS (
  SELECT DISTINCT ON (appid)
    appid,
    payload ->> 'genre' AS genre_list
  FROM raw.steam_steamspy_json
  WHERE COALESCE(payload ->> 'genre', '') <> ''
  ORDER BY appid, fetched_at DESC
)
SELECT DISTINCT
  latest.appid AS game_id,
  TRIM(g.genre_name) AS genre_name
FROM latest
CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(latest.genre_list, ',')) AS g(genre_name)
WHERE TRIM(g.genre_name) <> ''
