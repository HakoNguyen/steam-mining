import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from ingestion.collector import (collect_batch, collect_reviews, get_minio_client, get_target_appids)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    # Bị Steam giới hạn (429) thì phải chờ lâu mới được gỡ; thử lại sau 5 phút chỉ làm bị khóa lâu hơn
    'retry_delay': timedelta(minutes=30)
}

def run_daily_reviews_collection():
    target_appids = get_target_appids()
    client = get_minio_client()
    print(f'Found {len(target_appids)} target appids')

    # GetAppReviews không key dùng chung giới hạn thấp cho mỗi IP: nghỉ 1,5 giây như DAG universe
    collect_batch(target_appids, [collect_reviews], client, pause=1.5)
    
with DAG(
    'steam_daily_reviews_ingestion',
    default_args=default_args,
    description='Daily Game Reviews Ingestion Pipeline',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,  # lượt chạy tay + lượt theo lịch cùng lúc sẽ vượt giới hạn của Steam
    tags=['steam', 'ingestion', 'daily', 'reviews']
) as dag: 
    task_collect_reviews = PythonOperator(
        task_id='task_collect_daily_reviews',
        python_callable=run_daily_reviews_collection,
    )

    task_collect_reviews