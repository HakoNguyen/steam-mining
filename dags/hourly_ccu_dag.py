import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import collect_ccu, get_minio_client, get_target_appids

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2, 
    'retry_delay': timedelta(minutes=5),
}

def run_hourly_ccu_collection():
    target_appids = get_target_appids(limit=20)
    client = get_minio_client()

    print(f"Airflow CCU: Starting for {len(target_appids)} games")
    for appid in target_appids:
        collect_ccu(appid, client)

with DAG(
    'steam_hourly_ccu_ingestion',
    default_args=default_args,
    description='Hourly CCU collection via Airflow',
    schedule_interval='0 * * * *', 
    catchup=False,
    tags=['steam', 'ingestion', 'hourly', 'ccu'],
) as dag:
    
    task_collect_ccu = PythonOperator(
        task_id='task_collect_hourly_ccu',
        python_callable=run_hourly_ccu_collection,
    )
    
    task_collect_ccu

    