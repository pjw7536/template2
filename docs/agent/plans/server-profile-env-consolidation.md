# ExecPlan: 서버 profile 환경변수 통합

## 목표
- API server runtime overlay를 제거한다.
- local과 server 설정을 파일명과 Compose 계층에서 명확히 분리한다.
- OIDC 개발 서버와 운영 서버가 server common 뒤에 각자 profile env를 사용한다.
- 파일 구조를 변경하더라도 기존 profile에서 적용되던 non-empty env 값은 유지한다.
- 로컬 dev/test dummy 계약과 Airflow 공통 env 계약은 유지한다.

## 현재 상태
- API 공통 정책은 `env/api.common.env`에 있다.
- 로컬 dummy 연결은 `env/api.local.env`에 있다.
- 서버는 공유 provider 설정과 profile별 DB·인증·credential 경계를 명시적으로 분리한다.

## 범위
- 수정: API env 계층, OIDC/prod Compose, Make 검증 진입점, env/운영 문서, Compose 검증 스크립트.
- 제거: API server runtime env와 관련 변수·검증 명칭.
- 제외: API request/response, DB schema, auth 방식, dev dummy endpoint, ADFS 인증서 mount.

## 설계
- local API env 적용 순서는 `api.common.env` → `api.local.env`로 고정한다.
- 서버 API env 적용 순서는 `api.common.env` → `api.server.common.env` → `api.server.<profile>.env`로 고정한다.
- 공유 provider endpoint는 server common, OIDC/prod의 DB·origin·OIDC·credential은 각 server profile에 둔다.
- 값 이전은 기존 Compose 적용 순서의 최종값을 기준으로 하며, 기존에 값이 있던 key를 빈 값으로 바꾸지 않는다.
- Airflow trigger token과 OCR 내부 token은 `api.common.env`에 두고 dev가 필요한 값만 override한다.
- OIDC/prod는 서로 독립된 profile 검증 명령을 사용한다.
- test는 `api.common.env` → `api.test.env` 흐름을 유지한다.

## 실행 단계
- [x] runtime env의 서버 종속 key를 OIDC/prod profile로 이동한다.
- [x] 공통 내부 token을 API common env로 이동한다.
- [x] Compose와 Make에서 runtime overlay 참조를 제거한다.
- [x] 서버 profile별 검증 스크립트와 Make target을 추가한다.
- [x] configuration/inventory/integrations/operations 문서를 동기화한다.
- [x] dev/OIDC/prod/test Compose와 문서·스크립트 검증을 실행한다.
- [x] env 파일명을 local/server 축으로 변경하고 server common key 소유권을 분리한다.
- [x] offsite skill과 관련 문서의 local env 경로를 동기화한다.
- [x] 기존 local/OIDC/prod의 non-empty 최종값을 새 env 계층에 복원한다.
- [x] profile별 이전 값 보존 여부와 Compose 병합 결과를 다시 검증한다.

## 검증
- 통과: `bash scripts/agent/check_compose_configs.sh`
- 통과: `npm run agent:audit:docs`
- 통과: dev/OIDC/prod/test `docker compose ... config --quiet`
- 통과: `bash -n scripts/validate_server_profile_env.sh`
- 통과: API common/server common/server profile 간 key 중복 0건과 필수 key 소유권 확인
- 통과: dev dummy ADFS/RAG/OpenWebUI/Mail/Jira endpoint 유지 확인
- 통과: agent test 12건과 docs audit
- 통과: `git diff --check`
- 통과: 기존 local/OIDC/prod의 non-empty 최종값 비교. 의도된 `EMAIL_EXCLUDED_SUBJECT_PREFIXES` wildcard 변경 외 차이 0건.
- 통과: 값 복원 후 dev/OIDC/prod Compose config와 docs audit 재검증.
- 예상 차단: OIDC 관련 필수값은 기존 env에서도 비어 있었으므로 추측해 채우지 않는다.

## 위험과 대응
- 위험: runtime 파일 제거 과정에서 서버 종속 key가 누락될 수 있다.
- 대응: 제거 전 runtime key와 OIDC/prod profile key를 집합으로 대조한다.
- 위험: OIDC 실행이 prod의 미완성 설정 때문에 막힐 수 있다.
- 대응: profile별 Make 검증 target을 분리한다.
- 위험: offsite dev가 사내 endpoint로 fallback할 수 있다.
- 대응: dev dummy endpoint와 token override를 유지하고 dev Compose를 검증한다.
- 위험: profile 필수값이 비어 있으면 서버가 잘못된 설정으로 시작할 수 있다.
- 대응: 각 서버 기동·빌드 전에 해당 profile 검증을 실행한다.

## 진행 기록
- 2026-08-21: 사용자 결정에 따라 API server runtime overlay를 제거하고 OIDC/prod profile 완결 구조로 전환했다.
- 2026-08-21: Airflow는 common env, API는 common+profile 구조로 단순화했다.
- 2026-08-21: profile key 이동, offsite dev wiring, 네 Compose 진입점, 문서와 스크립트 검증을 완료했다.
- 2026-08-21: 사용자 확정에 따라 `common+local`과 `common+server.common+server profile` 구조로 최종 정리했다.
- 2026-08-21: 사용자 요청에 따라 기존 Compose 적용 순서에서 유효했던 non-empty 값을 새 파일에도 그대로 보존하기로 했다.
- 2026-08-21: local/OIDC/prod의 기존 non-empty 값을 모두 복원했다. profile 검증은 기존부터 비어 있던 OIDC 5개 항목만 남아 예상대로 차단됐다.
