MODEL (
  name dw.dim_tag,
  kind FULL,
  grain tag_key,
  description 'User tag (SteamSpy); khóa là hash của tên nên ổn định giữa các lần dựng lại',
  audits (not_null(columns := (tag_key, tag_name)), unique_values(columns := (tag_key)))
);

SELECT DISTINCT
  @GENERATE_SURROGATE_KEY(tag_name) AS tag_key,
  tag_name
FROM staging.stg_game_tags
