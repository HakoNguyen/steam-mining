MODEL (
  name staging.stg_game_tags,
  kind VIEW,
  grain (game_id, tag_name),
  description 'Mỗi dòng là 1 cặp game - tag (user tag), có số vote và thứ hạng vote trong game'
);

WITH latest AS (
  SELECT DISTINCT ON (appid)
    appid,
    payload -> 'tags' AS tags
  FROM raw.steam_steamspy_json
  WHERE JSONB_TYPEOF(payload -> 'tags') = 'object'
  ORDER BY appid, fetched_at DESC
)
SELECT
  latest.appid AS game_id,
  t.tag_name,
  t.vote_count::INT AS vote_count,
  ROW_NUMBER() OVER (PARTITION BY latest.appid ORDER BY t.vote_count::INT DESC, t.tag_name) AS vote_rank
FROM latest
CROSS JOIN LATERAL JSONB_EACH_TEXT(latest.tags) AS t(tag_name, vote_count)
