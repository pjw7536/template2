# ExecPlan: Airflow 3 업그레이드와 배포

## 목표
- Airflow 3.3.2를 이미지·DAG·인증·Portal 연동·배포 도구와 로컬 환경에 적용한다.
- 실제 실행 검증 후 확인된 운영 대상에 배포한다.

## 현재 상태
- 이미지·DAG·Helm·Portal client는 Airflow 3.3.2/API v2로 구성하며 Helm chart 1.22.0과 LocalExecutor를 사용한다.
- Keycloak SSO는 FAB provider와 사용자별 Viewer·User·Admin 역할을 사용한다.
- Portal은 서버 계정으로 JWT를 발급받아 API v2를 조회한다.
- 로컬 DB migration이 완료됐으며 기존 DAG 실행 이력 1,148건이 유지된다. DB·Secret은 local/shared/runtime/airflow-3-backup에 보관한다.
- 운영 대상은 [서버 목록](../../../deploy/shared/docs/infrastructure/servers.md#서버-목록)의 `khinfow01`이며 클러스터 Worker 추가는 사용자 확인이다. Ready·Airflow 배포 적용은 별도 확인이 필요하고, 실제 운영 배포는 사용자가 CP1에서 명령을 직접 실행한다.
- 현재 환경은 로컬 kind만 접근할 수 있다. 사내 SSH·API는 연결 시간 초과다.

## 범위
- apps/airflow, deploy/airflow, local/airflow, 관련 local/shared 실행·검증 도구를 수정한다.
- Portal의 Airflow API client·설정·테스트와 관련 문서·도구 검사를 함께 맞춘다.
- 기존 데이터·비밀키·realm·사용자 역할은 보존하며 DB 초기화·임의 운영 노드 선택은 하지 않는다.

## 설계
- 공식 Airflow 3.3.2 이미지와 호환 FAB·Standard provider를 고정한다.
- API server·독립 DAG processor와 JWT 입력을 구성하며 LocalExecutor·기존 스토리지 계약을 유지한다.
- Keycloak callback과 FAB 초기화를 Airflow 3에 맞추고 동일한 앱 역할 정책을 유지한다.
- Portal은 인증 token을 얻어 Airflow API v2로 목록·실행 이력을 조회한다.
- DAG는 공개 SDK·Standard provider를 사용하고 실행 의미와 일정은 유지한다.

## 실행 단계
- [x] 공식 계약과 현재 이미지·배포·API·로컬 연결을 대조한다.
- [x] 이미지·DAG·SSO·배포 도구와 테스트를 수정한다.
- [x] Portal API v2 client와 로컬 설정·검증을 수정한다.
- [x] 관련 문서·정적 검사와 회귀 테스트를 맞춘다.
- [x] Airflow 3 실제 이미지·로컬 기동·DAG·SSO·Portal 통합을 검증한다.
- [ ] 사용자가 CP1에서 준비한 이미지·실제 env로 khinfow01에 배포하고 운영 결과를 확인한다.

## 검증
- Airflow DAG·인증·배포 도구 단위 테스트 및 tooling 회귀 검사.
- Docker Compose api에서 Portal Airflow client 테스트와 Django 검사.
- Helm render·서버 checkout 경계·env 검사·문서 감사·diff 검사.
- 실제 Airflow 3 이미지에서 DAG import, task 실행, DB migration, SSO·역할, API v2·JWT, 로그·연동 검증.
- 확인 결과: 이미지 내 DAG·OIDC 11개, 배포·OIDC 46개, Compose Portal 9개 테스트 통과. tooling 구조·checkout 36개와 라우팅 4개 통과.
- 실제 로컬 검증: API v2 import 오류 0건, SDK·Execution API·XCom task 성공, SSO 3역할·역할 회수·익명 거부·Portal 조회 성공. 대표 DAG → Portal → RAG Outbox 처리 성공.
- 사내 전용 BigDataQuery·ODBC artifact 빌드와 운영 CA·Keycloak client·실제 env 검증은 CP1/빌드 호스트에서 수행해야 한다.

## 위험과 대응
- 기존 로컬 DB의 major migration은 백업·호환성 확인 후 실행하며 데이터와 Fernet 키를 유지한다.
- 사내 운영 접속·Worker·이미지 공급·CA·env가 확인되지 않으면 운영 적용은 대기하고 독립 가능한 검증을 진행한다.
- 버전별 FAB 경로·callback·API 응답·schedule 의미는 공식 소스와 실제 컨테이너에서 검증한다.
