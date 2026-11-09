# Airflow Keycloak client 등록 도구

`setup_client.py`는 기존 Keycloak realm에 Airflow 전용 client·callback·역할·mapper를 등록합니다.
Python 표준 라이브러리로 관리 호스트에서 실행하며 Kubernetes Job을 생성하지 않습니다.

입력은 Airflow 운영 env와 실행 프로세스의 Keycloak 관리자 연결값입니다.
기존 realm·다른 앱 client·사용자 역할을 유지하고, client secret이 기존 값과 다르면 중단합니다.

비밀값 준비·등록 명령·로그인과 API 검증은 [Airflow SSO 절차](../../../docs/03-deploy.md#keycloak-로그인)를 따릅니다.
