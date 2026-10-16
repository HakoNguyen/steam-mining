import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import (collect_batch, collect_ccu, collect_reviews, collect_steamspy,
                                 collect_store_browse, get_minio_client)
from ingestion.universe import get_universe_appids, sync_game_universe

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def run_store_browse():
    appids = get_universe_appids()
    failed = collect_store_browse(appids, get_minio_client())
    ok = len(appids) - len(failed)
    print(f"[Universe] collect_store_browse: {ok}/{len(appids)} OK")
    if appids and ok / len(appids) < 0.8:
        raise RuntimeError(f"[Universe] Store browse only {ok}/{len(appids)}. Check network access to Steam.")


def run_steamspy():
    collect_batch(get_universe_appids(), [collect_steamspy], get_minio_client(), pause=1)


def run_ccu():
    collect_batch(get_universe_appids(), [collect_ccu], get_minio_client())


def run_reviews():
    collect_batch(get_universe_appids(), [collect_reviews], get_minio_client(), pause=1.5)


with DAG(
    'steam_weekly_universe_ingestion',
    default_args=default_args,
    description='Weekly ~2.000 game (SteamSpy top owners) cho Data Mining: Store browse, SteamSpy, CCU, Reviews',
    schedule_interval='0 1 * * 1',  # 01:00 UTC thứ Hai
    catchup=False,
    max_active_runs=1,
    tags=['steam', 'ingestion', 'weekly', 'universe', 'mining'],
) as dag:

    task_sync_universe = PythonOperator(task_id='task_sync_universe', python_callable=sync_game_universe)
    task_store_browse = PythonOperator(task_id='task_collect_store_browse', python_callable=run_store_browse)
    task_steamspy = PythonOperator(task_id='task_collect_steamspy', python_callable=run_steamspy)
    task_ccu = PythonOperator(task_id='task_collect_ccu', python_callable=run_ccu)
    task_reviews = PythonOperator(task_id='task_collect_reviews', python_callable=run_reviews)

    # Chạy lần lượt để không dồn request vào Steam cùng lúc
    task_sync_universe >> task_store_browse >> task_steamspy >> task_ccu >> task_reviews
