# 먼저 저장소 apps/airflow/image/Dockerfile.dependencies로 사내 의존성 이미지를 빌드한다.
ARG AIRFLOW_DEPENDENCY_IMAGE=apache/airflow:2.11.0
FROM ${AIRFLOW_DEPENDENCY_IMAGE}
COPY --chown=airflow:0 dags/ /opt/airflow/dags/
COPY --chown=airflow:0 plugins/ /opt/airflow/plugins/
COPY --chown=airflow:0 image/bootstrap-user.py /opt/airflow/bootstrap-user.py
