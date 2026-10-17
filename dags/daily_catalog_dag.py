import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.catalog import sync_daily_catalog

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'steam_daily_catalog_sync',
    default_args=default_args,
    description='Daily Top 50 game catalog (seed list chung cho mọi DAG)',
    schedule_interval='0 0 * * *',
    catchup=False,
    tags=['steam', 'ingestion', 'daily', 'catalog'],
) as dag:

    task_sync_catalog = PythonOperator(
        task_id='task_sync_daily_catalog',
        python_callable=sync_daily_catalog,
    )

    task_sync_catalog
