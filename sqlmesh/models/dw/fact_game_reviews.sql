MODEL (
  name dw.fact_game_reviews,
  kind INCREMENTAL_BY_UNIQUE_KEY (unique_key review_id),
  cron '@daily',
  grain review_id,
  description 'Mỗi dòng là 1 review duy nhất; review mới thì thêm, review đã có thì cập nhật bản mới nhất (MERGE)',
  audits (
    not_null(columns := (review_id, game_id, voted_up)),
    unique_values(columns := (review_id))
  )
);

SELECT DISTINCT ON (review_id)
  review_id,
  game_id,
  voted_up,
  review_text,
  votes_up,
  weighted_vote_score,
  review_created_at,
  author_playtime_min,
  review_language,
  fetched_at AS last_seen_at
FROM staging.stg_reviews
WHERE fetched_at BETWEEN @start_tstz AND @end_tstz
ORDER BY review_id, fetched_at DESC
