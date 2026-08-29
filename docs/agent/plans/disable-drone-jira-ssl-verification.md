# ExecPlan: Drone Jira SSL 검증 비활성화

## 목표
- 모든 독립 API profile에서 Jira HTTP client의 SSL 인증서 검증을 비활성화한다.

## 현재 상태
- Django는 `DRONE_JIRA_VERIFY_SSL`을 지원하며 env가 없으면 기본값 `true`를 사용한다.
- local/OIDC/prod/test API env에는 해당 변수가 없다.

## 범위
- 수정: `env/overlays/{local,oidc,prod,test}/api.env`.
- 추가: 이 ExecPlan.
- 제외: Django settings와 Jira client 코드, credential, URL.

## 설계
- 각 profile의 Drone Jira 설정 구역에 `DRONE_JIRA_VERIFY_SSL=false`를 독립적으로 명시한다.
- 코드 기본값은 유지하고 Compose env 주입으로만 동작을 변경한다.

## 실행 단계
- [x] 네 API env에 동일한 변수를 추가한다.
- [x] env key와 Compose 병합 결과를 검증한다.

## 검증
- `make env-profile-key-check`
- `bash scripts/agent/check_compose_configs.sh`
- dev/OIDC/prod/test Compose의 API 환경변수 값을 확인한다.
- `git diff --check`

## 위험과 대응
- 위험: Jira 서버 인증서를 검증하지 않아 중간자 공격 탐지가 약해진다.
- 대응: 사용자 요청에 따라 profile env에 명시적으로 제한하며 코드 기본값 `true`는 유지한다.

## 진행 기록
- 2026-08-29: 모든 API profile에 `DRONE_JIRA_VERIFY_SSL=false`를 추가하기로 했다.
- 2026-08-29: env key, dev/OIDC/prod/test Compose 병합, 문서 audit와 diff 검증을 통과했다.
