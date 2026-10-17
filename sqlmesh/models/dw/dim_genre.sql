MODEL (
  name dw.dim_genre,
  kind FULL,
  grain genre_key,
  description 'Thể loại game (Steam Store genres); khóa là hash của tên nên ổn định giữa các lần dựng lại',
  audits (not_null(columns := (genre_key, genre_name)), unique_values(columns := (genre_key)))
);

SELECT DISTINCT
  @GENERATE_SURROGATE_KEY(genre_name) AS genre_key,
  genre_name
FROM staging.stg_game_genres
