MODEL (
    name staging.stg_game_catalog,
    kind VIEW,
    grain (catalog_date, chart, game_id),
    description 'Bảng xếp hạng Steam mỗi ngày: most_played (nhiều người chơi nhất, toàn cầu) và top_sellers (bán chạy nhất, Steam Việt Nam). Mỗi (ngày, bảng) chỉ lấy 1 nguồn: Steam chính thức > SteamSpy (trước 20/10/2026) > chép lại hôm trước > danh sách cố định',
    column_descriptions (
        catalog_date = 'Ngày chụp bảng xếp hạng (UTC)',
        chart = 'most_played | top_sellers',
        ranking_order = 'Thứ hạng trong bảng xếp hạng',
        game_id = 'Steam appid',
        game_title = 'Tên game lúc chụp (chỉ có ở top_sellers và SteamSpy); tên chuẩn lấy từ dw.dim_game',
        concurrent_players = 'most_played: số người đang chơi lúc chụp',
        peak_ccu_today = 'most_played: đỉnh người chơi trong ngày theo Steam',
        source = 'steam_charts | steam_store_topsellers | steamspy_top100in2weeks | carry_over | fallback'
    )
);

WITH ranked AS (
    SELECT
        catalog_date, chart, ranking_order, game_id, game_title, concurrent_players, peak_ccu_today, source,
        RANK() OVER (
            PARTITION BY catalog_date, chart
            ORDER BY CASE source
                WHEN 'steam_charts' THEN 0 WHEN 'steam_store_topsellers' THEN 0
                WHEN 'steamspy_top100in2weeks' THEN 1 WHEN 'carry_over' THEN 2 ELSE 3 END
        ) AS source_rank
    FROM raw.game_catalog_daily
)
SELECT
    catalog_date,
    chart,
    ranking_order,
    game_id,
    game_title,
    concurrent_players,
    peak_ccu_today,
    source
FROM ranked
WHERE source_rank = 1
