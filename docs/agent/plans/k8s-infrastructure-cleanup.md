# ExecPlan: Kubernetes 전환 후 인프라 정리

## 목표
- Portal 소스 변경 없이 폐기 Compose 구성과 사용 종료가 확인된 코드를 제거한다.

## 현재 상태
- 시작 HEAD: 989b6f63185ce76519d00131efff5c0e5e45fc7c. 작업 트리는 깨끗하다.
- kind·이미지 빌드·로컬 DB/API 검사·CI는 Docker를 사용한다.
- 이전 Compose 전용 env·Nginx·모니터링 설정과 검사가 남아 있다.

## 범위
- local·deploy·Makefile·tooling·현재 문서·관련 agent 규칙을 정리한다.
- apps/portal 전체, 실제 설정·DB·volume·런타임 파일은 보존한다.
- Airflow DAG·mock·독립 수동 도구와 Kubernetes 이미지 빌드는 유지한다.

## 설계
- Compose는 local/shared/compose/k8s-db.yml, k8s-check.yml, deploy/portal/compose/test.yml만 유지한다.
- 환경 검사는 Kubernetes 공개 예시·로컬·CI 입력을 검증한다. Airflow·Monitoring·Headlamp 실제 입력은 기존 배포 검사에 위임한다.
- API·DB·인증 계약과 로컬 env 합성 순서는 변경하지 않는다.
- 삭제 근거: 폐기 Compose에서만 사용하는 설정 또는 공통 Kubernetes 실행으로 대체되고 호출자가 없는 래퍼.

## 실행 단계
- [x] 폐기된 추적 파일과 실행 진입점 제거
- [x] env·Compose 검사 및 회귀 테스트 갱신
- [x] 현재 문서·agent 규칙·스킬 동기화
- [x] 검증 및 Portal 무변경 확인

## 검증
- make tooling-test, make audit
- 배포 도구 단위 테스트, make compose-check env-profile-key-check k8s-check
- make server-check APP=all
- make check-api makemigrations-check
- 관련 스킬 quick_validate.py, git diff --check
- 실행 파일·현재 문서의 삭제 경로 참조 검사, apps/portal diff 없음 확인

## 위험과 대응
- 삭제된 env를 검사가 계속 요구할 수 있다: 공개 예시만 둔 fixture와 서버 선택 checkout 검사로 확인한다.
- 실행 중인 환경은 재배포·종료하지 않는다. Compose 검사는 가짜 입력을 사용한다.
- Git 제외 파일은 제거하지 않는다. 과거 ExecPlan과 Portal 내부 잔여 참조는 예외로 보고한다.

## 진행 기록
- 2026-09-16: 사용자 계획 승인. 구현 시작.

- 2026-09-16: 폐기 Compose·전용 env·Nginx·Monitoring·중복 래퍼 등 추적 파일 40개 삭제. 실제 설정과 Git 제외 데이터는 보존했다.
- 2026-09-16: Compose 검사를 유지한 세 구성과 가짜 입력으로 변경. env 검사는 Kubernetes 예시·로컬 공통 입력·CI만 요구한다. 폐기 profile 검사를 제거하고 Helm 앱은 전용 검사에 위임한다.
- 2026-09-16: 현재 문서와 스킬 명령을 갱신했다. 삭제된 파일 경로의 활성 참조는 0건이며 Portal 내부·과거 기록은 예외로 유지한다.
- 2026-09-16: 작업 중 별도의 portal-agent-scope 문서 작업이 나타났다. 루트 AGENTS 개편과 새 deploy/local 지침, Portal 내부 AGENTS·README 변경은 그 작업의 변경으로 보존했다. 이 작업에서는 apps/portal에 쓰기를 수행하지 않았다.

## 검증 결과

| 검사 | 결과 |
| --- | --- |
| PATH에 저장소 .tools/bin을 추가한 make tooling-test | 62개 통과, Airflow·Monitoring·Headlamp 배포 도구 및 서버 선택 checkout 포함 |
| env fixture에서 실제 k8s/build env 제외 후 환경 테스트 | 35개 통과 |
| make audit의 도구 단위 테스트 | 24개 통과 |
| make compose-check env-profile-key-check k8s-check | 통과 |
| make server-check APP=all | 6개 서버 앱 원본 검사 통과 |
| make check-api makemigrations-check | Django check 이상 없음, migration 변경 없음 |
| make k8s-health | 전체 앱 준비 상태·공개 진입점 정상 |
| frontend/backend 경계·hotspot·UI·문서 감사 | 별도 실행 통과 |
| make audit / audit-layout 재확인 | 기존 apps/web와 루트 airflow 잔여 디렉터리 때문에 실패. 이번 작업에서 제거하지 않음 |
| 수정한 스킬 2개 quick_validate.py | 통과 |
| 셸 문법·수정 Python 문법·git diff --check | 통과 |

클러스터 재배포·재생성·통합 데이터 생성·DB 초기화는 수행하지 않았다. 이미지 빌드와 전체 Django 테스트는 변경 범위상 재실행하지 않았다.
Portal 내부 잔여 경로는 앱 README·관리 명령 README와 seed_drone_dummy_data.py 주석에 있으며 이 작업에서 수정하지 않는다.
로그는 /tmp/k8s-cleanup-*.log에 남겼다. 커밋·push는 수행하지 않았다.
