# ExecPlan: profile env 카테고리 정리

## 목표
- local/OIDC/prod/test의 모든 서비스 env를 의미 단위 카테고리로 정리한다.
- 각 카테고리 시작 전에 한국어 주석과 빈 줄을 두어 서버 운영자가 빠르게 찾을 수 있게 한다.
- 기존 환경변수 key/value와 Compose 최종 적용 결과를 보존한다.

## 현재 상태
- env는 `env/overlays/<profile>/<service>.(config|secret).env` 구조로 독립 관리된다.
- 파일별 header와 일부 구분 주석은 있으나 서비스·profile 간 카테고리 순서가 일관되지 않다.
- 한 파일 안의 중복 key는 `scripts/validate_env_profile_keys.sh`가 차단한다.

## 범위
- 수정: `env/overlays` 아래의 모든 env 파일.
- 추가: 이 ExecPlan.
- 제외: 환경변수 key/value, Compose 연결, runtime 코드, Kubernetes/Argo CD manifest.

## 설계
- API는 Django, DB, Web URL, 보안, OIDC, 업무 데이터, 외부 연동과 runtime 정책으로 분류한다.
- Web은 Node runtime, site/backend, MinIO, 외부 링크로 분류한다.
- Airflow, MinIO, Grafana는 서비스 연결·운영 정책·인증 정보로 분류한다.
- config와 secret은 각각의 성격에 맞는 카테고리를 사용하고 profile 간 순서를 통일한다.
- 파일 header는 유지하고 기존 중간 주석은 표준 카테고리 주석으로 교체한다.

## 실행 단계
- [x] 변경 전 파일별 key/value snapshot을 생성한다.
- [x] 서비스별 카테고리 규칙으로 env를 재정렬한다.
- [x] 카테고리 주석과 빈 줄 형식을 점검한다.
- [x] key/value 동등성과 전체 env/Compose 계약을 검증한다.

## 검증
- 파일별 정렬된 `KEY=VALUE` hash 변경 전후 비교
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.test.yml config --quiet`
- `make oidc-profile-env-check`와 `make prod-profile-env-check`의 예상 빈 값만 확인
- `npm run agent:audit:docs`
- `git diff --check`

## 위험과 대응
- 위험: 재정렬 중 key/value가 누락되거나 값의 특수문자가 바뀔 수 있다.
- 대응: 원문 assignment line을 그대로 이동하고 파일별 정렬 hash를 비교한다.
- 위험: profile마다 카테고리가 달라 운영자가 같은 변수를 찾기 어려울 수 있다.
- 대응: 동일 service는 공통 category 순서를 사용하고 빈 category만 생략한다.

## 진행 기록
- 2026-08-29: 모든 profile의 config/secret env를 값 변경 없이 카테고리별로 정리하기로 했다.
- 2026-08-29: 30개 env의 모든 key를 서비스별 표준 카테고리로 분류하고 기존 assignment 행을 그대로 재정렬했다.
- 2026-08-29: 정렬 전후 파일별 key/value hash가 일치하며 env key, dev/OIDC/prod/test Compose와 문서 검증을 통과했다.
- 2026-08-29: OIDC/prod server 검증은 기존부터 비어 있는 OIDC/ADFS 필수값만 동일하게 보고함을 확인했다.
- 2026-08-29: 후속 Airflow backend proxy 전환에서 빈 Web secret env 3개를 제거했으며, 최종 27개 env의 카테고리 형식을 유지했다.
- 2026-08-29: 후속 단일 env 통합에서 카테고리 형식을 유지한 채 최종 파일 수를 15개로 줄였다.
