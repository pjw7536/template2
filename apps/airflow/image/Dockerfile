# 먼저 저장소 apps/airflow/image/Dockerfile.dependencies로 사내 의존성 이미지를 빌드한다.
ARG AIRFLOW_DEPENDENCY_IMAGE=apache/airflow:2.11.0
FROM ${AIRFLOW_DEPENDENCY_IMAGE}
COPY --chown=airflow:0 dags/ /opt/airflow/dags/
COPY --chown=airflow:0 plugins/ /opt/airflow/plugins/
COPY --chown=airflow:0 image/bootstrap-user.py /opt/airflow/bootstrap-user.py
COPY --chown=airflow:0 image/webserver_config.py image/keycloak_security.py image/oidc_claims.py /opt/airflow/
# SSO가 사용하는 기존 이미지 의존성의 호환 범위를 빌드 시 확인한다.
RUN python -c "from importlib.metadata import version; from packaging.version import Version; assert version('apache-airflow') == '2.11.0'; assert Version('1.5.3') <= Version(version('apache-airflow-providers-fab')) < Version('2'); assert Version('1.3.1') <= Version(version('Authlib')) < Version('2')"
