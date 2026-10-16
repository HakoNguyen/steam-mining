MODEL (
  name dw.dim_time,
  kind FULL,
  grain time_key,
  description '24 giờ theo UTC, kèm giờ Việt Nam (UTC+7) và buổi trong ngày theo giờ Việt Nam',
  audits (unique_values(columns := (time_key)))
);

SELECT
  h AS time_key,
  h AS hour_utc,
  (h + 7) % 24 AS hour_vn,
  CASE
    WHEN (h + 7) % 24 BETWEEN 5 AND 11 THEN 'Sáng'
    WHEN (h + 7) % 24 BETWEEN 12 AND 17 THEN 'Chiều'
    WHEN (h + 7) % 24 BETWEEN 18 AND 22 THEN 'Tối'
    ELSE 'Đêm'
  END AS day_part_vn
FROM GENERATE_SERIES(0, 23) AS t(h)
