MODEL (
  name staging.stg_reviews,
  kind VIEW,
  grain (review_id, fetched_at),
  description 'Mỗi dòng là 1 review trong 1 lần lấy; cùng review có thể lặp lại giữa các ngày'
);

SELECT
  r.appid AS game_id,
  r.fetched_at,
  rv.review ->> 'recommendationid' AS review_id,
  rv.review ->> 'review' AS review_text,
  (rv.review ->> 'voted_up')::BOOLEAN AS voted_up,
  (rv.review ->> 'votes_up')::INT AS votes_up,
  (rv.review ->> 'weighted_vote_score')::NUMERIC AS weighted_vote_score,
  TO_TIMESTAMP((rv.review ->> 'timestamp_created')::BIGINT) AS review_created_at,
  (rv.review -> 'author' ->> 'playtime_forever')::INT AS author_playtime_min,
  rv.review ->> 'language' AS review_language
FROM raw.steam_reviews_json AS r
CROSS JOIN LATERAL JSONB_ARRAY_ELEMENTS(r.payload -> 'reviews') AS rv(review)
