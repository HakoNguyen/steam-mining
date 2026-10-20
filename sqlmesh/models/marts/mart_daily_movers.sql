MODEL (
  name marts.mart_daily_movers,
  kind VIEW,
  grain (report_date, game_id),
  description 'Biến động top 50 nhiều người chơi nhất (bảng most_played) giữa ngày gần nhất đã đủ dữ liệu và ngày liền trước: thay đổi CCU, thứ hạng, game vào/ra top 50, giảm giá sâu. Dùng cho bản tin thị trường',
  column_descriptions (
    report_date = 'Ngày báo cáo (ngày gần nhất đã đủ dữ liệu, UTC)',
    game_id = 'Steam appid',
    game_title = 'Tên game',
    status = 'new_entry: mới vào top 50 | dropped_out: rơi khỏi top 50 | stayed: vẫn trong top 50',
    rank_today = 'Thứ hạng trong top 50 ngày báo cáo',
    rank_yesterday = 'Thứ hạng trong top 50 ngày trước',
    rank_change = 'Số bậc tăng (dương) hoặc giảm (âm)',
    peak_ccu_today = 'CCU cao nhất trong ngày báo cáo',
    peak_ccu_yesterday = 'CCU cao nhất ngày trước',
    peak_ccu_change_pct = 'Phần trăm thay đổi CCU cao nhất so với ngày trước',
    snapshots_today = 'Số lần đo CCU trong ngày báo cáo (tối đa ~24); ít lần đo thì CCU cao nhất kém tin cậy',
    snapshots_yesterday = 'Số lần đo CCU ngày trước',
    price_vnd = 'Giá (VND) có hiệu lực trong ngày báo cáo',
    discount_pct = 'Phần trăm giảm giá trong ngày báo cáo',
    is_deep_discount = 'Đang giảm giá >= 50%'
  )
);

WITH report AS (
  SELECT MAX(p.full_date) AS report_date
  FROM dw.fact_daily_game_performance AS p
  JOIN staging.stg_game_catalog AS c
    ON c.game_id = p.game_id AND c.catalog_date = p.full_date AND c.chart = 'most_played'
), top_today AS (
  SELECT c.game_id, c.ranking_order
  FROM staging.stg_game_catalog AS c, report AS r
  WHERE c.catalog_date = r.report_date AND c.chart = 'most_played'
), top_yesterday AS (
  SELECT c.game_id, c.ranking_order
  FROM staging.stg_game_catalog AS c, report AS r
  WHERE c.catalog_date = r.report_date - 1 AND c.chart = 'most_played'
), games AS (
  SELECT game_id FROM top_today
  UNION
  SELECT game_id FROM top_yesterday
)
SELECT
  r.report_date,
  gm.game_id,
  d.game_title,
  CASE
    WHEN ty.game_id IS NULL THEN 'new_entry'
    WHEN tt.game_id IS NULL THEN 'dropped_out'
    ELSE 'stayed'
  END AS status,
  tt.ranking_order AS rank_today,
  ty.ranking_order AS rank_yesterday,
  ty.ranking_order - tt.ranking_order AS rank_change,
  p_today.peak_ccu AS peak_ccu_today,
  p_yest.peak_ccu AS peak_ccu_yesterday,
  ROUND(100.0 * (p_today.peak_ccu - p_yest.peak_ccu) / NULLIF(p_yest.peak_ccu, 0), 1) AS peak_ccu_change_pct,
  p_today.snapshot_count AS snapshots_today,
  p_yest.snapshot_count AS snapshots_yesterday,
  p_today.price_vnd,
  p_today.discount_pct,
  COALESCE(p_today.discount_pct >= 50, FALSE) AS is_deep_discount
FROM games AS gm
CROSS JOIN report AS r
LEFT JOIN top_today AS tt ON tt.game_id = gm.game_id
LEFT JOIN top_yesterday AS ty ON ty.game_id = gm.game_id
LEFT JOIN dw.fact_daily_game_performance AS p_today
  ON p_today.game_id = gm.game_id AND p_today.full_date = r.report_date
LEFT JOIN dw.fact_daily_game_performance AS p_yest
  ON p_yest.game_id = gm.game_id AND p_yest.full_date = r.report_date - 1
LEFT JOIN dw.dim_game AS d ON d.game_id = gm.game_id AND d.valid_to IS NULL
