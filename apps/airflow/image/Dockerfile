# 먼저 저장소 apps/airflow/image/Dockerfile.dependencies로 사내 의존성 이미지를 빌드한다.
ARG AIRFLOW_DEPENDENCY_IMAGE=apache/airflow:3.3.2-python3.12
FROM ${AIRFLOW_DEPENDENCY_IMAGE}
LABEL org.opencontainers.image.title="Etch Airflow" \
      org.opencontainers.image.description="Apache Airflow runtime with Etch plugins and Keycloak sign-in. DAG files are deployed separately."
# DAG는 이미지에 넣지 않는다. 배포가 Worker의 DAG 폴더를 /opt/airflow/dags에 읽기 전용으로 연결한다.
COPY --chown=airflow:0 plugins/ /opt/airflow/plugins/
COPY --chown=airflow:0 image/bootstrap-user.py /opt/airflow/bootstrap-user.py
COPY --chown=airflow:0 image/webserver_config.py image/keycloak_security.py image/oidc_claims.py image/keycloak_profile.py /opt/airflow/
# parser와 LocalExecutor task가 DAG 폴더의 공통 모듈을 동일하게 읽는다.
ENV PYTHONPATH=/opt/airflow:/opt/airflow/dags
# SSO가 사용하는 기존 이미지 의존성의 호환 범위를 빌드 시 확인한다.
RUN python -c "from importlib.metadata import version; from packaging.version import Version; assert version('apache-airflow') == '3.3.2'; assert Version('3') <= Version(version('apache-airflow-providers-fab')) < Version('4'); assert Version('1.3.1') <= Version(version('Authlib')) < Version('2')"
