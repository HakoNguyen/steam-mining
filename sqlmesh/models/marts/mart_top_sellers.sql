MODEL (
  name marts.mart_top_sellers,
  kind VIEW,
  grain (catalog_date, game_id),
  description 'Top 50 game bán chạy nhất trên Steam Việt Nam của ngày mới nhất (bảng top_sellers), so với ngày trước; kèm giá, giảm giá, thể loại và game sắp ra mắt (đang cho đặt trước)',
  column_descriptions (
    catalog_date = 'Ngày chụp bảng xếp hạng (UTC)',
    rank = 'Thứ hạng bán chạy',
    rank_yesterday = 'Thứ hạng ngày trước (NULL: mới vào top 50)',
    rank_change = 'Số bậc tăng (dương) hoặc giảm (âm) so với ngày trước',
    game_id = 'Steam appid',
    game_title = 'Tên game',
    genres = 'Các thể loại, cách nhau bởi dấu phẩy',
    is_free = 'Game miễn phí',
    price_vnd = 'Giá hiện tại (VND); NULL khi chưa mở bán giá trên trang game',
    price_initial_vnd = 'Giá gốc (VND)',
    discount_pct = 'Phần trăm giảm giá',
    release_date = 'Ngày phát hành',
    is_upcoming = 'Chưa phát hành (đang cho đặt trước) tại ngày chụp',
    most_played_rank = 'Thứ hạng trong top 50 nhiều người chơi cùng ngày (NULL: không có mặt)'
  )
);

WITH latest AS (
  SELECT MAX(catalog_date) AS catalog_date FROM staging.stg_game_catalog WHERE chart = 'top_sellers'
), genres AS (
  SELECT b.game_id, STRING_AGG(dg.genre_name, ', ' ORDER BY dg.genre_name) AS genres
  FROM dw.bridge_game_genre AS b
  JOIN dw.dim_genre AS dg ON dg.genre_key = b.genre_key
  GROUP BY b.game_id
)
SELECT
  l.catalog_date,
  t.ranking_order AS rank,
  y.ranking_order AS rank_yesterday,
  y.ranking_order - t.ranking_order AS rank_change,
  t.game_id,
  COALESCE(g.game_title, t.game_title) AS game_title,
  ge.genres,
  g.is_free,
  g.price_vnd,
  g.price_initial_vnd,
  g.discount_pct,
  g.release_date,
  COALESCE(g.release_date > l.catalog_date, FALSE) AS is_upcoming,
  mp.ranking_order AS most_played_rank
FROM staging.stg_game_catalog AS t
JOIN latest AS l ON l.catalog_date = t.catalog_date
LEFT JOIN staging.stg_game_catalog AS y
  ON y.game_id = t.game_id AND y.chart = 'top_sellers' AND y.catalog_date = l.catalog_date - 1
LEFT JOIN staging.stg_game_catalog AS mp
  ON mp.game_id = t.game_id AND mp.chart = 'most_played' AND mp.catalog_date = l.catalog_date
LEFT JOIN dw.dim_game AS g ON g.game_id = t.game_id AND g.valid_to IS NULL
LEFT JOIN genres AS ge ON ge.game_id = t.game_id
WHERE t.chart = 'top_sellers'
