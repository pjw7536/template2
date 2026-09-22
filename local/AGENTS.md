# 외부 PC 개발 환경 지침

## 소유권과 탐색
- local/<app>은 외부 PC용 설정·mock·실행 도구를 소유한다. 공통 정의는 deploy에서 참조하며 서버 도구가 local에 의존하게 하지 않는다.
- local/shared/k8s는 공통 기반과 Kustomize 집계 진입점이다. Portal·Keycloak·Headlamp·mock 원본은 각각 local/portal·local/keycloak·local/headlamp·local/adfs_dummy에 둔다. 다른 앱의 원본을 Portal에 넣지 않는다.
- Portal 코드 작업에서 이 영역은 실행·env·mock·외부 연동 계약에 영향이 있을 때만 읽는다. 대상 앱 설정 → 관련 mock → 필요한 shared 실행 도구 순서로 탐색한다.
- 사내망 연결 없이 실행 가능한 흐름을 유지하고 외부 endpoint·credential은 env로 주입한다.
- auth/RAG/assistant/mail 변경은 루트 `.codex/skills/offsite-dev-contract-sync/SKILL.md`를 적용한다. 파일 마운트 변경은 ../deploy/AGENTS.md의 데이터 계약도 확인한다.

## 현재 실행 계약
- 루트 `make dev`는 kind의 전체 앱과 별도 Docker PostgreSQL을 기동한다. 상세 준비·명령은 README.md를 필요한 만큼 읽는다.
- 기존 환경의 Portal 소스 변경 반영은 `make k8s-rebuild APP=portal`, mock 변경 반영은 `make k8s-rebuild APP=mock`을 사용한다.
- Django 검사·명령은 shared/compose/k8s-check.yml의 일회성 api 컨테이너에서 실행한다. make test-api는 표준 test env, check-api·makemigrations-check는 합성된 로컬 env를 사용한다.
- Portal API env는 portal/env/api.env → api-k8s.env → 생성된 shared/runtime/api-overrides.env 순서로 합성한다. portal/scripts/build-local-api-env.sh를 재사용하고 Pod YAML에 중복 주입하지 않는다.
- shared/runtime의 생성 파일과 DB·호스트 데이터는 보존한다. 설정 수정으로 데이터 초기화나 클러스터 재생성을 자동 수행하지 않는다.

## 검증
- 설정 변경의 범위에 맞춰 루트 `make k8s-render-local`, `make env-profile-key-check ENV_APP=portal ENV_PROFILE=local`, `make compose-check` 중 관련 검사를 실행한다.
- 통합 실행 검증은 필요한 경우 준비된 로컬 환경에서 `make k8s-smoke`를 사용한다. 준비되지 않았으면 실행 불가 사유를 보고한다.
- 서버·공통 도구 의존 방향을 변경하면 `node --test apps/tooling/tests/server-checkout.test.cjs`로 local 없는 서버 검사를 확인한다.
