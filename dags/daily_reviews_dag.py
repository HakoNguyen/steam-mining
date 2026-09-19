import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import (collect_reviews, get_minio_client, get_target_appids)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

def run_daily_reviews_collection():
    target_appids = get_target_appids(limit=50)
    client = get_minio_client()
    print(f'Found {len(target_appids)} target appids')

    for appid in target_appids: 
        collect_reviews(appid, client)
    
with DAG(
    'steam_daily_reviews_ingestion',
    default_args=default_args,
    description='Daily Game Reviews Ingestion Pipeline',
    schedule_interval='@daily',
    catchup=False,
    tags=['steam', 'ingestion', 'daily', 'reviews']
) as dag: 
    task_collect_reviews = PythonOperator(
        task_id='task_collect_daily_reviews',
        python_callable=run_daily_reviews_collection,
    )

    task_collect_reviews