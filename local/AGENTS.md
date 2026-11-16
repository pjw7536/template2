# 외부 PC 개발 환경 지침

## 소유권과 탐색

- `local/<app>`은 외부 PC 설정·mock·실행 도구를 소유한다. 공통 정의는 deploy를 참조하고 서버 도구가 local에 의존하게 하지 않는다.
- `shared/k8s`는 기반·Kustomize 집계만 담당한다. 앱별 원본은 `portal`, `keycloak`, `headlamp`, `adfs_dummy` 등 해당 소유 폴더에 두고 다른 앱 설정을 Portal에 넣지 않는다.
- Portal에서 이 영역은 실행·env·mock·외부 계약에 영향이 있을 때 읽는다. 대상 앱 설정 → 관련 mock → 필요한 shared 도구 순으로 확인한다.
- auth/RAG/assistant/mail 계약은 루트 `offsite-dev-contract-sync` 스킬, 파일 마운트는 [deploy 데이터 계약](../deploy/AGENTS.md#환경과-데이터-계약)을 함께 따른다.

## 실행·환경·데이터

- 루트 `make dev`는 kind 전체 앱과 별도 Docker PostgreSQL을 기동한다. 준비·명령은 [README](README.md)에서 선택하고 기존 환경을 재사용한다.
- 소스 반영은 `make k8s-rebuild APP=portal`, mock은 `make k8s-rebuild APP=mock`을 사용한다.
- Django 명령은 `shared/compose/k8s-check.yml`의 일회성 api 컨테이너에서 실행한다. `make test-api`는 표준 test env, `check-api`·`makemigrations-check`는 합성한 로컬 env를 사용한다.
- Portal API env는 `portal/env/api.env` → `api-k8s.env` → 생성된 `shared/runtime/api-overrides.env` 순서다. `portal/scripts/build-local-api-env.sh`를 재사용하고 Pod YAML에 중복 주입하지 않는다.
- `shared/runtime` 생성 파일과 DB·호스트 데이터를 보존한다. 설정 수정을 이유로 데이터 초기화·클러스터 재생성을 자동 수행하지 않는다.

## 검증

- 변경에 맞춰 루트 `make k8s-render-local`, `make env-profile-key-check ENV_APP=portal ENV_PROFILE=local`, `make compose-check` 중 필요한 검사를 선택한다.
- 통합 검증은 준비된 환경에서 필요한 경우 `make k8s-smoke`를 사용한다. 준비되지 않았으면 실행 불가 사유를 보고한다.
- 서버·공통 도구 의존 방향 변경에는 `node --test apps/tooling/tests/server-checkout.test.cjs`로 local 없는 서버 검사를 확인한다.
