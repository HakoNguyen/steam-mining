MODEL (
  name dw.bridge_game_genre,
  kind FULL,
  grain (game_id, genre_key),
  description 'Quan hệ nhiều-nhiều game - thể loại; dựng lại mỗi lần nên thể loại bị gỡ sẽ tự biến mất',
  audits (unique_combination_of_columns(columns := (game_id, genre_key)))
);

SELECT
  game_id,
  @GENERATE_SURROGATE_KEY(genre_name) AS genre_key
FROM staging.stg_game_genres
