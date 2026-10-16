import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import (collect_batch, collect_steamspy, collect_store_details, get_minio_client, get_target_appids)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2, 
    'retry_delay': timedelta(minutes=5),
}

def run_weekly_metadata_collection():
    target_appids = get_target_appids()
    client = get_minio_client()

    print(f"[Airflow Weekly DAG] Collecting Metadata & SteamSpy for"f" {len(target_appids)} games...")
    collect_batch(target_appids, [collect_store_details, collect_steamspy], client)

with DAG(
    'steam_weekly_metadata_ingestion',
    default_args=default_args,
    description='Daily metadata collection via Airflow (game mới vào catalog cần metadata trong ngày)',
    schedule_interval='@daily',
    catchup=False,
    tags=['steam', 'ingestion', 'daily', 'metadata'],
) as dag:
    
    task_collect_metadata = PythonOperator(
        task_id='task_collect_weekly_metadata',
        python_callable=run_weekly_metadata_collection,
    )
    
    task_collect_metadata