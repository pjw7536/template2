# ExecPlan: Portal 선택 checkout의 로그인 등록 명령 수정

## 목표
- Portal 전용 서버 checkout에서 문서의 keycloak-portal-client-setup 명령이 실행되게 한다.
- 기존 등록 도구와 env 입력을 유지하고 새 실행 도구를 만들지 않는다.

## 현재 상태
- 수정 전 Portal 선택에는 deploy/portal과 deploy/shared만 포함되어 공식 등록 명령에 필요한 Keycloak 실행 파일과 공통 등록 자산이 누락됐다.
- Portal env가 있어도 실행 파일 누락으로 실패하는 것을 실제 sparse checkout으로 재현했다.
- 현재는 필수 지원 경로 4개를 포함하고 Keycloak env·앱 소스·local 없이 등록 명령의 전체 실행 흐름을 검증했다.
- 기존 미커밋 변경과 서버 선택 전환의 백업 보호를 보존한다.

## 범위
- deploy/shared/apps.json의 Portal 지원 경로와 app-paths.py의 경로 조회.
- 서버 checkout 회귀 테스트와 관련 사용 안내.
- 등록 스크립트 구현·env 계약·클러스터 설정은 변경하지 않는다.

## 설계
- 앱 목록 원본에 선택적 supportPaths를 두고 Portal에 필요한 Keycloak scripts·k8s/claims·k8s/oidc·k8s/server만 지정한다.
- 지원 경로는 다른 앱의 env나 앱 소스를 포함하지 않는 배포 하위 경로로 제한한다.
- --names는 선택 앱 이름만 반환하므로 Portal 검사에 Keycloak 검사·env를 추가하지 않는다.
- 기존 Makefile 명령과 등록 도구는 그대로 사용한다. Portal 등록에 필요한 env는 Portal api.env 하나다.

## 실행 단계
- [x] Portal 전용 checkout에서 공식 등록 명령 실패 회귀 테스트 추가
- [x] 최소 지원 경로를 앱 목록과 선택 조회에 연결
- [x] 안내 동기화 및 관련 검사

## 검증
- 실제 sparse checkout 후 앱 소스·local·Keycloak env 없는 상태에서 등록 흐름 실행.
- Kubernetes 명령은 모의 실행해 입력·대상 context·Portal Job 호출을 확인하며 실제 클러스터는 변경하지 않는다.
- `PATH="$PWD/.tools/bin:$PATH" node --test apps/tooling/tests/server-checkout.test.cjs`
- `PATH="$PWD/.tools/bin:$PATH" make tooling-test`
- `PATH="$PWD/.tools/bin:$PATH" make server-check APP=portal`, `make audit-docs`, `git diff --check`

## 위험과 대응
- 지원 코드 선택 때문에 Keycloak 전체 배포나 credential이 포함되지 않도록 파일 범위를 검사한다.
- 그룹 선택과 --with-source의 기존 동작을 유지한다. 기존 백업 보호 회귀도 함께 실행한다.

## 진행 기록
- 2026-10-27: 기존 실행 도구 재사용과 경로 목록 수정으로 범위를 한정했다.
- 2026-10-27: 공식 Makefile 명령을 Portal 전용 sparse checkout에서 실행하는 회귀 테스트가 수정 전 실행 파일 누락으로 실패하고 수정 후 통과했다. Portal env 선택·context 강제·Job 완료 대기 호출을 모의 Kubernetes 명령으로 확인했다.
- 2026-10-27: 서버 checkout 24개와 전체 tooling 84개 테스트, Portal 서버 원본 검사, 문서 검사와 diff 공백 검사를 통과했다. 지원 경로에 env·앱 소스·상위 이동 등을 넣는 잘못된 입력 6가지도 차단했다. 실제 클러스터는 변경하지 않았다.
