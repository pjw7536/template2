"""외부 업무 API 없이 scheduler·LocalExecutor·DB·로그 경로를 검증하는 로컬 DAG입니다."""

from datetime import datetime, timezone

from airflow import DAG
from airflow.operators.python import PythonOperator


def verify_runtime():
    """실제 task 프로세스에서 metadata DB 연결을 확인합니다."""
    from airflow.settings import engine
    from sqlalchemy import text

    with engine.connect() as connection:
        assert connection.execute(text('SELECT 1')).scalar() == 1
    print('로컬 플랫폼 task·metadata DB 확인 완료')


with DAG('local_platform_smoke', schedule=None, start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
         catchup=False, is_paused_upon_creation=True, tags=['local', 'smoke']) as dag:
    PythonOperator(task_id='verify_runtime', python_callable=verify_runtime)
