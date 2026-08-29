# ExecPlan: profile env 단일 파일 통합

## 목표
- profile별 서비스 설정을 `<service>.env` 한 파일로 단순화한다.
- local/OIDC/prod/test의 독립 관리와 기존 key/value, Compose 최종 동작을 보존한다.
- Argo CD 도입 시 별도 Secret 파일을 전제로 하지 않는 단일 env 계약을 제공한다.

## 현재 상태
- API, Airflow, MinIO, Grafana는 `*.config.env`와 `*.secret.env`로 나뉘어 있다.
- Web은 secret 파일이 제거됐지만 `web.config.env` 이름을 사용한다.
- Compose, 검증 스크립트, 운영 문서와 agent 지침이 기존 파일명을 참조한다.

## 범위
- 통합: `env/overlays/{local,oidc,prod,test}`의 서비스 env 파일.
- 수정: Compose env_file 연결, Makefile, env 검증 스크립트, 관련 운영·개발 문서와 agent 지침.
- 제외: 환경변수 key/value 의미, Django/Web runtime 코드, Kubernetes/Argo CD manifest 생성.

## 설계
- 최종 파일은 local 4개, OIDC 5개, prod 5개, test 1개로 구성한다.
- 기존 config 카테고리 뒤에 인증·credential 카테고리를 합치고 한 파일 안의 중복 key를 금지한다.
- server profile 검증은 `api.env` 한 개를 받고 같은 폴더의 `airflow.env`와 공용값을 비교한다.
- local dummy endpoint와 credential 값은 변경하지 않고 파일 경로만 전환한다.
- Argo CD는 단일 env 파일 기반 ConfigMap 계약으로 문서화하고, 보안 저장소 도입 시 별도 분리를 다시 설계한다.

## 실행 단계
- [x] 변경 전 profile/service별 key/value snapshot을 생성한다.
- [x] config/secret을 `<service>.env`로 통합한다.
- [x] Compose, Makefile과 검증 스크립트를 새 경로로 전환한다.
- [x] 문서와 agent 지침의 기존 파일명 잔재를 정리한다.
- [x] env/Compose/local dummy/agent 검증을 실행한다.

## 검증
- profile/service별 정렬된 `KEY=VALUE` hash 변경 전후 비교
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.test.yml config --quiet`
- dev/OIDC/prod/test Compose의 주요 service env key 확인
- `npm run agent:audit:docs`
- agent test와 변경한 skill quick validation
- `git diff --check`

## 위험과 대응
- 위험: 통합 중 key/value 누락이나 덮어쓰기가 발생할 수 있다.
- 대응: 변경 전후 assignment hash와 중복 key validator를 함께 확인한다.
- 위험: Compose 또는 운영 명령이 삭제된 파일명을 계속 참조할 수 있다.
- 대응: 저장소 전체 기존 파일명 검색과 모든 profile Compose config 검증을 수행한다.
- 위험: local dummy wiring이 끊길 수 있다.
- 대응: dev Compose의 API/Web/Airflow/MinIO env 적용 결과와 dummy endpoint 값을 확인한다.

## 진행 기록
- 2026-08-29: 보안을 별도 관리하지 않는 운영 방침에 따라 서비스별 env를 단일 파일로 통합하기로 했다.
- 2026-08-29: 27개 config/secret env를 15개 서비스 env로 통합하고 profile/service별 assignment hash가 모두 일치함을 확인했다.
- 2026-08-29: dev/OIDC/prod/test와 standalone Airflow Compose, Django system check, 문서·agent test와 offsite skill validation을 통과했다.
- 2026-08-29: local dummy endpoint와 credential은 변경하지 않고 `api.env` 단일 주입으로 전환했다.
