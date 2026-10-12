"""
Schema Migration Utility for Postgres DWH
Adds created_at and updated_at audit columns to existing DWH tables,
plus dim_game feature columns used by mining/.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.db_connect import get_db_connection

def migrate_schema():
    conn = get_db_connection()
    cursor = conn.cursor()
    print("[Migration] Adding audit columns to PostgreSQL DWH...")

    alter_statements = [
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE dim_tag ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE bridge_game_tag ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE bridge_game_tag ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE dim_genre ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE bridge_game_genre ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE dim_date ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE dim_time ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE fact_player_snapshot ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE fact_player_snapshot ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE fact_daily_game_performance ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE fact_daily_game_performance ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;",
        # Mining features (SteamSpy: positive/negative/owners/playtime; Store: languages/categories)
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS positive INT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS negative INT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS owners_min BIGINT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS owners_max BIGINT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS avg_playtime_forever INT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS median_playtime_forever INT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS languages_count SMALLINT;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS has_multiplayer BOOLEAN;",
        "ALTER TABLE dim_game ADD COLUMN IF NOT EXISTS has_coop BOOLEAN;"
    ]

    for stmt in alter_statements:
        try:
            cursor.execute(stmt)
        except Exception as e:
            print(f"  [Warning] {stmt} -> {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("[Migration] Schema migration completed successfully! 🎉")

if __name__ == "__main__":
    migrate_schema()
