# ExecPlan: env 기능 카테고리 재정렬

## 목표
- 모든 서비스 env에서 인증값을 별도 하단에 모으지 않고 관련 기능 설정과 함께 배치한다.
- 가능한 범위에서 `4e745ef1568bfda897f711e7aca21e2f665a57cf` 시점의 변수 순서를 따른다.
- 현재 key/value와 Compose 동작은 그대로 유지한다.

## 현재 상태
- 15개 profile/service env는 단일 파일 구조로 통합돼 있다.
- API, Airflow, MinIO, Grafana의 credential이 파일 하단 인증 카테고리로 분리된 부분이 있다.
- 기준 커밋은 공통·환경별 파일이 나뉘어 있어 현재 서비스 파일에 직접 대응하지 않는다.

## 범위
- 수정: `env/overlays/{local,oidc,prod,test}`의 15개 env 파일.
- 추가: 이 ExecPlan.
- 제외: 환경변수 key/value, 파일명, Compose 연결, runtime 코드와 문서 계약.

## 설계
- 기준 커밋의 큰 순서인 runtime → Django/DB → origin/security/auth → domain data → 외부 연동 순서를 유지한다.
- password/token/header는 Django, DB, Airflow, Email, OpenWebUI, RAG, Mail, Drone, Knox 등 관련 기능 카테고리에 합친다.
- MinIO와 Grafana는 기준 커밋 순서대로 계정 → 정책/접근키 → URL 순으로 정리한다.
- Web은 Node → backend → MinIO → site → 외부 링크 순으로 정리한다.
- 신규 변수는 가장 가까운 현재 기능 카테고리에 배치한다.

## 실행 단계
- [x] 변경 전 파일별 assignment hash를 기록한다.
- [x] 기준 커밋과 현재 key를 기능 카테고리에 매핑한다.
- [x] 15개 env의 순서와 주석만 재작성한다.
- [x] assignment hash와 env/Compose 계약을 검증한다.

## 검증
- 파일별 정렬된 `KEY=VALUE` hash 변경 전후 비교
- 모든 key가 정확히 한 카테고리에 포함되는지 확인
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.test.yml config --quiet`
- `git diff --check`

## 위험과 대응
- 위험: 기준 커밋의 분할 파일 순서를 현재 단일 파일에 합칠 때 key가 누락될 수 있다.
- 대응: 현재 파일의 assignment 집합과 재작성 대상 key 집합을 일대일 비교하고 hash를 검증한다.
- 위험: 같은 기능의 profile별 순서가 달라질 수 있다.
- 대응: API는 하나의 공통 category/key 순서를 사용하고 없는 key만 생략한다.

## 진행 기록
- 2026-08-29: 기준 커밋 순서를 참고해 인증값을 기능 카테고리에 통합하기로 했다.
- 2026-08-29: 15개 env를 기능별로 재정렬하고 모든 `KEY=VALUE` assignment의 변경 전후 hash가 일치함을 확인했다.
- 2026-08-29: env profile key, dev/OIDC/prod/test Compose, 문서 inventory, `git diff --check` 검증을 통과했다.
