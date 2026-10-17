MODEL (
  name dw.bridge_game_tag,
  kind FULL,
  grain (game_id, tag_key),
  description 'Quan hệ nhiều-nhiều game - tag, kèm số vote và thứ hạng vote (dùng cho FP-Growth: top 10 tag/game)',
  audits (unique_combination_of_columns(columns := (game_id, tag_key)))
);

SELECT
  game_id,
  @GENERATE_SURROGATE_KEY(tag_name) AS tag_key,
  vote_count,
  vote_rank
FROM staging.stg_game_tags
