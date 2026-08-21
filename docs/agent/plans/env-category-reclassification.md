# ExecPlan: 환경변수 카테고리 재분류

## 목표
- API와 Airflow 환경변수를 도메인 소유권과 실행 profile에 맞게 재배치한다.
- 환경변수 key 계약과 dev/OIDC/prod 환경의 최종 유효 값은 유지한다.
- 서버 profile이 별도 공통/runtime overlay 없이 자체 실행 계약을 갖게 한다.

## 현재 상태
- `api.common.env`는 모든 profile이 공유하는 정책과 안전 기본값을 관리한다.
- `api.local.env`는 로컬 dummy 외부계와 개발용 값을 관리한다.
- `api.server.common.env`는 두 서버가 공유하는 비밀이 아닌 provider endpoint를 관리한다.
- `api.server.oidc.env`와 `api.server.prod.env`는 각 서버의 DB·origin·인증·credential·실행 설정을 관리한다.
- Airflow는 모든 환경에서 `airflow.common.env`를 사용한다.

## 범위
- 수정: `env/api*.env`, OIDC/prod Compose, 환경 설정 문서와 검증 스크립트.
- 검증: dev dummy wiring, dev/OIDC/prod/test Compose 렌더.
- 제외: 환경변수 key rename, endpoint 경로 변경, API/DB/auth 계약 변경.

## 설계
- `env/api.common.env`에는 모든 profile이 공유할 안전한 기본값과 내부 공통 token만 둔다.
- local profile은 `apps/adfs_dummy` endpoint와 개발용 token을 override한다.
- server common에는 공유 provider endpoint를, OIDC/prod profile에는 DB·origin·OIDC·credential을 둔다.
- API env 적용 순서는 local은 공통 → local, 서버는 공통 → server common → server profile로 고정한다.
- Airflow trigger token은 API common과 Airflow common에서 동일하게 유지한다.
- DB, migration, public API, auth callback 변화는 없다.

## 실행 단계
- [x] 공통 env의 도메인 정책과 profile 소유값을 분리한다.
- [x] dev profile에 local DB와 dummy 외부계 값을 명시한다.
- [x] OIDC/prod profile에 서버별 설정 key를 직접 배치한다.
- [x] 서버 공통/runtime overlay와 Compose 참조를 제거한다.
- [x] 문서 inventory와 운영 env 목록을 새 계층에 맞춘다.
- [x] profile별 최종 주입값과 중복·누락을 검증한다.

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- `npm run agent:audit:docs`
- `docker compose -f docker-compose.test.yml config --quiet`
- `git diff --check`
- profile별 key 목록과 dev dummy endpoint 유지 여부 확인

## 위험과 대응
- 위험: profile 이동 과정에서 endpoint나 header key가 누락될 수 있다.
- 대응: 제거한 overlay의 key 집합과 두 서버 profile의 key 집합을 대조한다.
- 위험: offsite dev가 사내 endpoint로 fallback할 수 있다.
- 대응: dev profile에서 RAG, OpenWebUI, Mail, Jira dummy endpoint를 명시적으로 유지한다.
- 위험: profile 필수값이 비어 기동 후 외부 연동이 실패할 수 있다.
- 대응: OIDC/prod 기동 전에 각 profile 전용 검증 target을 실행한다.

## 진행 기록
- 2026-08-19: key rename 없이 도메인 섹션과 profile 소유권을 재분류했다.
- 2026-08-21: 사용자 결정에 따라 중간 overlay 계층을 제거하고 common+profile 구조로 단순화했다.
- 2026-08-21: OIDC/prod key 집합, common 중복 0건과 dev dummy endpoint 유지 여부를 검증했다.
- 2026-08-21: local/server 파일명과 server common/provider, server profile/credential 소유권을 확정했다.
