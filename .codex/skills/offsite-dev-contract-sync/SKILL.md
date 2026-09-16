---
name: offsite-dev-contract-sync
description: |
  외부망(offsite) 개발 환경에서 auth/RAG/assistant/mail contract 변경 시
  local/portal/k8s, local/portal/env, local/adfs_dummy 간 정합성을 유지하는 스킬.
---

# offsite-dev-contract-sync

## 목적
corporate network 없이도 로컬 개발 환경이 계속 동작하도록 mock과 dev wiring을 함께 유지한다.

## 사용할 때
- auth / OIDC / ADFS contract를 변경할 때
- RAG endpoint contract를 변경할 때
- assistant dummy mode 연동을 변경할 때
- mail sandbox endpoint를 변경할 때
- 전체 로컬 Kubernetes 기준 실행 가능성을 유지해야 할 때

## 환경 전제
- `local/AGENTS.md`를 읽고 변경된 호출부·env·mock부터 확인한다. 공통 실행 도구는 연결·env 합성에 영향이 있을 때만 읽는다.
- offsite 개발은 `make dev`로 kind 전체 앱을 실행한다. 공통 실행 도구는 `local/shared/scripts/k8s.py`다.
- dummy service는 `local/adfs_dummy`에 있다.
- API 입력은 `local/portal/env/api.env` → `api-k8s.env` → 생성된 runtime override 순서로 합성하고 MinIO client credential을 추가한다. API·migration·seed는 같은 Secret을 사용하며 Pod YAML에서 중복 주입하지 않는다.
- 인증은 로컬 Keycloak, RAG·LLM·메일·Jira는 `local/adfs_dummy`를 사용한다.
- assistant dummy mode는 `ASSISTANT_DUMMY_MODE=1`로 제어한다.
- kind와 외부 PostgreSQL은 Docker `kind` network를 사용한다. 로컬 DB·API 검사 Compose는 `local/shared/compose`에 있다.

dummy 주요 endpoint 예시:
- auth/OIDC: discovery/login/logout/callback 관련 endpoint
- RAG: `/rag/search`, `/rag/insert`, `/rag/delete`, `/rag/index-info`
- Mail sandbox: `/mail/*`

## 점검 대상
contract가 바뀌면 아래를 함께 점검한다.

- `local/adfs_dummy`
- `local/portal/env/api.env`
- `local/portal/env/api-k8s.env`와 관련 env 합성 입력(생성된 runtime 파일은 직접 편집하지 않는다)
- `local/portal/k8s`
- Django 설정의 env var 참조부
- auth/rag/assistant/mail 호출부

## 작업 절차
1. 변경된 contract 식별
   - request field name
   - response shape
   - endpoint path
   - auth callback path
   - timeout/host/base URL
2. 실제 호출부 확인
   - Django service layer
   - serializer/client wrapper
   - dummy service handler
3. dev wiring 동기화
   - `local/portal/env/api.env`의 URL, mode flag와 credential
   - Kubernetes Secret·Service 연결과 `local/shared/scripts/k8s_config.py`의 runtime override
   - mock endpoint path
4. 로컬 실행 가능성 점검
   - `make k8s-check`로 원본·설정 검사
   - corporate resource 없이 fallback 가능 여부
   - URL 하드코딩 여부
   - 기동 검증이 필요한 경우 기존 환경·데이터를 보존하며 `make dev` 후 `make k8s-smoke`로 확인

## 서버와의 경계

- 로컬 설정·mock은 local에 두고 공통 배포 정의를 복제하지 않는다.
- 경로·공통 도구를 바꾸면 `node --test apps/tooling/tests/server-checkout.test.cjs`로 local 없는 서버 검사를 확인한다.

## 핵심 규칙
- intranet URL 하드코딩 금지
- 외부 의존성 URL은 env var 유지
- contract 변경 시 mock도 함께 업데이트
- local dummy flow가 깨지지 않도록 유지

## 출력 방식
관련 변경 제안 시 아래를 포함한다.

- 변경된 contract 요약
- 함께 수정해야 할 파일 목록
- mock 반영 필요 여부
- dev env 반영 필요 여부
- 로컬 실행 위험 포인트

## 금지사항
- corporate network 연결을 전제로 한 설명
- dummy/mocking 경로를 무시한 contract 변경
- env var 대신 URL 하드코딩
