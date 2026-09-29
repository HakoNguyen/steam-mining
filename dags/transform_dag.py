import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.load_dimesions import run_dimension_update
from transformation.load_facts import run_fact_pipeline

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'retries': 2,
    'retry_delay': timedelta(minutes=5)
}

with DAG(
    'transformation_staging_to_warehouse',
    default_args=default_args,
    description='Transform Staging to Data Warehouse',
    schedule_interval='15 * * * * ',
    catchup=False,
    tags=['steam', 'transformation', 'warehouse', 'dimension', 'fact'],
) as dag:

    task_transform_dimensions = PythonOperator(
        task_id='task_transform_dimensions',
        python_callable=run_dimension_update,
    )

    task_transform_facts = PythonOperator(
        task_id='task_transform_facts',
        python_callable=run_fact_pipeline,
    )

    task_transform_dimensions >> task_transform_facts