import sys
from datetime import datetime, timedelta
from pathlib import Path
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from transformation.load_raw import run_raw_load

# SQLMesh nằm trong venv riêng (xem Dockerfile); project được mount vào /opt/airflow/sqlmesh
SQLMESH_RUN = "cd /opt/airflow/sqlmesh && /opt/sqlmesh-venv/bin/sqlmesh --gateway docker run"

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
    description='MinIO ➔ raw (incremental) ➔ SQLMesh (staging, dw, marts)',
    schedule_interval='15 * * * *',
    catchup=False,
    max_active_runs=1,  # không cho 2 lần sqlmesh run chạy chồng lên nhau
    tags=['steam', 'transformation', 'warehouse', 'sqlmesh'],
) as dag:

    task_load_raw = PythonOperator(
        task_id='task_load_raw',
        python_callable=run_raw_load,
    )

    task_sqlmesh_run = BashOperator(
        task_id='task_sqlmesh_run',
        bash_command=SQLMESH_RUN,
    )

    task_load_raw >> task_sqlmesh_run
