MODEL (
  name dw.dim_date,
  kind FULL,
  grain date_key,
  description 'Lịch tự sinh 2026-2027, không phụ thuộc dữ liệu',
  audits (unique_values(columns := (date_key)))
);

SELECT
  TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
  d::DATE AS full_date,
  EXTRACT(ISODOW FROM d)::INT AS day_of_week,
  TRIM(TO_CHAR(d, 'Day')) AS day_name,
  EXTRACT(WEEK FROM d)::INT AS week_of_year,
  EXTRACT(MONTH FROM d)::INT AS month,
  EXTRACT(QUARTER FROM d)::INT AS quarter,
  EXTRACT(YEAR FROM d)::INT AS year,
  EXTRACT(ISODOW FROM d) IN (6, 7) AS is_weekend
FROM GENERATE_SERIES('2026-01-01'::DATE, '2027-12-31'::DATE, INTERVAL '1 day') AS t(d)
