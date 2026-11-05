"""외부 업무 API 없이 scheduler·LocalExecutor·DB·로그 경로를 검증하는 로컬 DAG입니다."""

from datetime import datetime, timezone

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonOperator


def verify_runtime():
    """Task SDK로 실행 context와 XCom 왕복을 확인합니다."""
    from airflow.sdk import get_current_context

    context = get_current_context()
    task = context['ti']
    task.xcom_push(key='runtime-check', value='airflow-3')
    assert task.xcom_pull(task_ids='verify_runtime', key='runtime-check') == 'airflow-3'
    print('로컬 플랫폼 task·Execution API·XCom 확인 완료')


with DAG('local_platform_smoke', schedule=None, start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
         catchup=False, is_paused_upon_creation=True, tags=['local', 'smoke']) as dag:
    PythonOperator(task_id='verify_runtime', python_callable=verify_runtime)
