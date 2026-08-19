# ExecPlan: RAG 공통 Adapter 단일화

## 목표
- RAG index 이름, client 설정, search/insert/delete/index-info, 오류·취소·timeout과 dummy 연결을 하나의 adapter로 정리한다.
- Assistant와 Emails가 provider 세부 payload를 직접 다루지 않게 한다.

## 현재 상태
- `api.rag.services.config`는 `ASSISTANT_RAG_*`를 먼저 읽고 `RAG_*`로 fallback하며 env와 Django settings도 이중 조회한다.
- 잘못된 headers/index/group JSON은 빈 값으로 조용히 바뀐다.
- Assistant와 Emails에 RAG hit/permission/mailbox 정규화 wrapper가 중복돼 있다.

## 범위
- 수정: `api.rag`, Assistant/Emails RAG 소비 facade, settings/env, `apps/adfs_dummy`, Compose/docs/tests.
- 유지: 외부 `/rag/search|insert|delete|index-info` provider payload, permission group/mailbox filtering, cancellation fallback.
- 제외: Spider 관련 Assistant profile/context.

## 설계
- canonical env는 `RAG_SEARCH_URL`, `RAG_INSERT_URL`, `RAG_DELETE_URL`, `RAG_INDEX_INFO_URL`, `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`, `RAG_PERMISSION_GROUPS`, `RAG_PUBLIC_GROUP`, `RAG_HEADERS`, `RAG_TIMEOUT_SECONDS`이다.
- `ASSISTANT_RAG_*` fallback과 runtime `os.environ` 재조회는 제거하고 Django settings에서 검증된 immutable config를 주입한다.
- invalid JSON/type와 설정된 기능의 빈 URL/index는 시작 또는 호출 전에 명확한 config error로 실패한다.
- adapter method는 typed `search`, `insert_email`, `delete_document`, `get_index_info`이고 공통 HTTP/cancel/error mapping을 사용한다.
- provider snake_case payload는 외부 계약으로 adapter 내부에만 남기고 domain에는 normalized camelCase/read model을 반환한다.
- index allowlist 밖 요청은 provider 호출 전에 거절한다.
- DB/migration 변화는 없다.

## 실행 단계
- [x] 현재 provider/dummy 요청·응답과 error/cancel characterization을 고정한다.
- [x] strict config와 adapter를 추가하고 RAG facade를 명시적으로 고정한다.
- [x] Assistant를 adapter 소비로 전환하고 Emails의 무의미한 재-export wrapper를 제거한다.
- [x] env/dev dummy/Compose/docs를 canonical key로 동기화한다.
- [x] legacy env와 wrapper 참조 0건을 확인한다.

## 검증
- dev API container에서 `api.rag api.emails api.assistant` tests.
- dummy search/insert/delete/index-info smoke, connect/read timeout, cancel, invalid JSON/index tests.
- `docker compose -f docker-compose.dev.yml config`, migration drift와 전체 boundary audit.

## 위험과 대응
- 위험: 운영이 `ASSISTANT_RAG_*`만 설정한다.
- 대응: 배포 전 rendered config에서 legacy key 사용을 탐지하고 canonical env가 없으면 배포를 중단한다.
- 위험: normalized hit가 provider metadata를 누락한다.
- 대응: Emails/Assistant의 현재 source fixture 전체를 adapter contract test로 고정한다.

## 의존성과 복구
- 상위 계약: [마스터](repository-refactor-master-2026-08.md)와 [Platform Common](platform-common-health-errors-refactor.md). Emails와 Assistant의 선행 단계다.
- 복구: Assistant/Emails consumer를 먼저 이전 facade로 되돌린 뒤 RAG adapter와 env/dummy를 함께 revert한다. provider index data는 변경하지 않는다.

## 진행 기록
- 2026-08-18: `RAG_*`만 canonical env로 사용하고 외부 snake_case는 adapter 내부로 한정했다.
- 2026-08-18: 18단계를 완료했다. runtime env/`ASSISTANT_RAG_*` fallback을 제거하고 strict immutable `RagConfig`, allowlist와 search/insert/delete/index-info `RagAdapter`를 추가했다. Assistant는 adapter를 소비하고 Emails의 `rag_exports` 중복을 제거했다. Compose/dummy를 canonical index로 재생성해 네 endpoint smoke를 통과했으며 RAG·Emails·Assistant 132개 테스트, Compose render, migration drift와 backend boundary가 통과했다.
