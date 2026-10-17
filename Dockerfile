FROM apache/airflow:2.8.1-python3.11

# Thư viện cho collector và load_raw (trước đây cài lại mỗi lần container khởi động qua _PIP_ADDITIONAL_REQUIREMENTS)
RUN pip install --no-cache-dir minio curl-cffi python-dotenv

# Venv riêng cho SQLMesh, tách khỏi thư viện của Airflow (SQLMesh cần duckdb>=0.10, Airflow 2.8.1 ghim 0.9.2).
# Image Airflow đặt sẵn PIP_USER=true (cài vào ~/.local), phải tắt khi cài vào venv.
USER root
RUN python -m venv /opt/sqlmesh-venv \
 && PIP_USER=false /opt/sqlmesh-venv/bin/pip install --no-cache-dir "sqlmesh==0.236.3" psycopg2-binary \
 && chown -R airflow: /opt/sqlmesh-venv
USER airflow
