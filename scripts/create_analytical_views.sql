--- View 1: Top Trending Games (Xep hang theo CCU)
CREATE OR REPLACE VIEW vw_top_trending_games AS SELECT
g.game_id, 
g.game_title,
g.app_type,
g.price_vnd,
g.is_free,
g.publisher_name,
g.developer_name,
g.total_reviews,
p.date_key,
d.full_date,
p.peak_ccu,
p.avg_ccu,
p.min_ccu,
p.snapshot_count 
FROM fact_daily_game_performance p 
JOIN dim_game g ON p.game_id = g.game_id
JOIN dim_date d ON p.date_key = d.date_key;

--- View 2: Aggregated CCU by Genre (Tong hop CCU theo the loai)
CREATE OR REPLACE VIEW vw_ccu_by_genre_daily AS SELECT
d.full_date, 
p.date_key, 
gr.genre_name, 
COUNT(DISTINCT g.game_id) AS game_count,
SUM(p.peak_ccu) AS total_peak_ccu,
ROUND(AVG(p.avg_ccu), 2) AS avg_ccu_per_game,
MAX(p.peak_ccu) AS max_single_game_peak
FROM fact_daily_game_performance p 
JOIN dim_game g ON p.game_id = g.game_id
JOIN bridge_game_genre bgg ON g.game_id = bgg.game_id
JOIN dim_genre gr ON bgg.genre_id = gr.genre_id
JOIN dim_date d ON p.date_key = d.date_key
GROUP BY d.full_date, p.date_key, gr.genre_name;

--- View 3: Game Sentiment & Market Performance Matrix (phan khuc gia & diem review)
CREATE OR REPLACE VIEW vw_game_sentiment_matrix AS
SELECT 
    g.game_id,
    g.game_title,
    g.price_vnd,
    g.is_free,
    g.total_reviews,
    COALESCE(MAX(p.peak_ccu), 0) AS historical_peak_ccu,
    COALESCE(ROUND(AVG(p.avg_ccu), 2), 0) AS overall_avg_ccu,
    CASE 
        WHEN g.is_free THEN 'Free to Play'
        WHEN g.price_vnd = 0 THEN 'Free'
        WHEN g.price_vnd < 100000 THEN 'Budget (<100k)'
        WHEN g.price_vnd < 500000 THEN 'Mid-tier (100k-500k)'
        ELSE 'Premium (>500k)'
    END AS price_tier
FROM dim_game g
LEFT JOIN fact_daily_game_performance p ON g.game_id = p.game_id
GROUP BY g.game_id, g.game_title, g.price_vnd, g.is_free, g.total_reviews;