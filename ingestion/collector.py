from networkx.algorithms.centrality import reaching
import urllib.request
import json
import sqlite3
import datetime
import time

DB_PATH = "raw_ccu.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS raw_ccu (
            game_id INTEGER NOT NULL,
            snapshot_time TEXT NOT NULL, 
            player_count INTEGER NOT NULL, 
            PRIMARY KEY (game_id, snapshot_time)
        )
    """)
    conn.commit()
    conn.close()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'
}

def fetch_player_count(appid): 
    url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=5) as res: 
            data = json.loads(res.read().decode('utf-8'))
            return data.get('response', {}).get('player_count', 0)
    except Exception as e:
        print(f"error when fetching {appid}")
        return None 

def get_top_appids():
    url = "https://steamspy.com/api.php?request=top100in2weeks"
    try: 
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode('utf-8'))
            return [int(k) for k in data.keys() if k.isdigit()]
    except Exception as e: 
        print("Error getting top appids:")
        return [730, 570, 1086940, 271590, 1172470]

def run_collection_cycle():
    init_db()

    target_appids = get_top_appids()

    snapshot_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:00:00")
    print(f"[{snapshot_time}] Starting collection cycle for {len(target_appids)} games...")
    
    conn = sqlite3.connect(DB_PATH)
    cusor = conn.cursor()

    sucess = 0
    for appid in target_appids: 
        count = fetch_player_count(appid)
        if count is not None: 
            cusor.execute("""
            INSERT OR REPLACE INTO raw_ccu (game_id, snapshot_time, player_count)
            VALUES (?, ?, ?)
            """, (appid, snapshot_time, count))
            sucess +=1 
            time.sleep(0.2) # rate limit
    
    conn.commit()
    conn.close()
    print(f"[DONE] Inserted {sucess}/{len(target_appids)} records to {DB_PATH}")

if __name__ == "__main__":
    run_collection_cycle()