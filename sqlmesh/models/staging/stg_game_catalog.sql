MODEL (
    name staging.stg_game_catalog,
    kind VIEW, 
    grain (catalog_date, game_id),
    description 'Top 50 game mỗi ngày (SteamSpy top100in2weeks), chuẩn hóa tên cột'
);

SELECT 
    catalog_date,
    ranking_order,
    game_id, 
    game_title, 
    ccu_2weeks AS ccu_peak_yesterday,
    source
FROM raw.game_catalog_daily
