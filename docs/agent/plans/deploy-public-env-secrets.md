# ExecPlan: 운영 일반 설정과 비밀값 분리

## 목표
- 실제 env의 일반 설정을 Git에 포함하고 비밀값만 제외한다.

## 현재 상태
- 운영 env 8개는 Git 제외 상태이며 일부에 기존 비밀값이 있다.
- Bash 공용 로더와 Airflow·Keycloak Python 로더가 해당 파일을 읽는다.

## 범위
- env 분리, Git 규칙, 로더, Airflow 비밀값 초기화, 안내와 회귀 검사.

## 설계
- foo.env의 비밀 키는 빈 값으로 유지하고 foo.secrets.env에 기존 값을 보존한다.
- 로더는 실제 .env에만 인접 secrets 파일을 병합한다. example은 병합하지 않는다.
- 일반 설정 파일에 없는 키는 secrets 파일에서 거부한다.
- Secret 리소스 이름은 비밀값이 아니므로 일반 env에 남긴다.

## 실행 단계
- [x] 기존 비밀값 보존 및 일반 env Git 포함
- [x] 로더·초기화·문서 수정
- [x] 병합·Git 경계·서버 검사

## 검증
- 분리 전후 병합 값의 동일성, 누락·중복·알 수 없는 키와 비실행 검증.
- 관련 Python·Node 검사, server-check, git diff --check.

## 위험과 대응
- 비밀값은 출력하지 않고 파일 권한 0600으로 저장한다.
- 커밋·push 및 운영 서버 변경은 수행하지 않는다.
- 미확정 운영 입력은 추측하지 않는다.

## 진행 기록
- 2026-09-23: 작업 시작.
- 일반 env 8개를 Git 포함 대상으로 전환했다. Airflow·Keycloak·Portal API·MinIO의 비밀값 파일 4개는 Git 제외·0600으로 보존했다. 분리 전후 병합 값의 동일성을 검사했다.
- Bash 공용 로더와 Keycloak·Airflow 로더가 인접 비밀값 파일을 병합한다. Airflow init-secrets는 일반 env에 비밀값을 쓰지 않으며 기존 비밀값 파일을 덮어쓰지 않는다.
- Keycloak 예시 파일의 기존 비밀번호 값도 replace-me로 제거했다. 기존 Git 이력은 수정하지 않았다.
- 관련 Node 테스트 58개, shared Python 36개, Airflow Python 21개 통과. 전체 앱 6개의 server-check와 prod profile 검사, 셸 문법, git diff --check 통과.
- 값 비실행, 중복·알 수 없는 키 거부, 비밀값 누락 시 필수값 검사 실패, 초기화 시 기존 파일 보존과 파일 권한을 검증했다.
- 비밀값 중복 검색에서 CI api.env의 기존 테스트용 토큰 2개가 확인됐다. 운영 일반 env에는 해당 값을 남기지 않았고 CI 전용 fixture는 유지했다.
- 실제 서버 배포·로그인 검증은 수행하지 않았다. 기존 미확정 운영 입력은 그대로 남아 있다. 커밋·push는 하지 않았다.
