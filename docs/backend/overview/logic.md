# 백엔드 공통 로직 문서

## 개요
- 권한/접근 제어, 소속 변경, Emails, RAG/Assistant 흐름을 통합 요약합니다.
- 서비스 전반에서 공유되는 정책과 데이터 흐름을 빠르게 파악하는 목적입니다.

## 범위
- 백엔드만 대상 (apps/api)
- 대상 기능: 권한/접근제어, 소속변경(account), Emails(emails), RAG(rag/assistant)

## 권한/접근 제어

### 1) 기본 인증/특권 판별
- 대부분의 View는 `request.user.is_authenticated`를 직접 검사합니다.
- 특권 사용자: `is_superuser` 또는 `is_staff`면 권한 우회가 허용됩니다.

관련 코드 경로
- `apps/api/api/account/views.py`
- `apps/api/api/emails/views.py`
- `apps/api/api/account/services/utils.py`

### 2) 접근 가능한 user_sdwt_prod 계산
핵심 함수: `account/selectors.get_accessible_user_sdwt_prods_for_user`

흐름
1) 비로그인 → 빈 집합 반환
2) superuser → 시스템 전체 user_sdwt_prod 집합 반환
   - Affiliation, UserSdwtProdAccess, User 모델 값까지 합산
3) 일반 사용자 → 접근 행(UserSdwtProdAccess) + 본인 user_sdwt_prod
4) user_sdwt_prod가 없으면, pending 변경(UserSdwtProdChange)의 `to_user_sdwt_prod`를 포함

관련 코드 경로
- `apps/api/api/account/selectors.py`

### 3) 관리 권한(can_manage) 부여/회수
핵심 모델: `UserSdwtProdAccess`

흐름 (부여/회수)
1) `ensure_self_access`로 본인 그룹 접근 행을 보장
2) `can_manage` 권한 여부 체크
3) 부여: `UserSdwtProdAccess` 생성 또는 업데이트
4) 회수: 마지막 관리자 제거 방지

관련 코드 경로
- `apps/api/api/account/models.py`
- `apps/api/api/account/services/access.py`
- `apps/api/api/account/selectors.py`

### 4) Emails 접근 권한
핵심 정책
- staff/superuser는 전체 접근
- 일반 사용자는:
  - 접근 가능한 user_sdwt_prod 집합
  - 또는 sender_id(knox_id)가 일치하는 메일
- UNASSIGNED 메일함은 staff/superuser만 조회 가능

핵심 함수
- `emails/permissions.resolve_access_control`
- `emails/permissions.user_can_access_email`
- `emails/permissions.user_can_view_unassigned`

관련 코드 경로
- `apps/api/api/emails/permissions.py`
- `apps/api/api/emails/views.py`

### 5) Assistant/RAG permission_groups
핵심 정책
- 요청에 permission_groups가 없으면 기본값 생성:
  - `user.user_sdwt_prod`
  - `sender_id(knox_id)`
  - `rag-public`
- 요청에 포함된 그룹은 “접근 가능한 그룹”에 포함되어야 함
  - 접근 가능한 user_sdwt_prod + sender_id + rag-public

관련 코드 경로
- `apps/api/api/assistant/services/normalization.py`
- `apps/api/api/assistant/selectors.py`

## 소속 변경 (Account)

### 1) 핵심 모델
- `Affiliation`: 허용된 부서/라인/user_sdwt_prod 조합
- `UserSdwtProdChange`: 소속 변경 요청/승인 이력
- `ExternalAffiliationSnapshot`: 외부 예측 소속 스냅샷
- `User`: 현재 소속 상태 저장 (`user_sdwt_prod`, `department`, `line`)

관련 코드 경로
- `apps/api/api/account/models.py`

### 2) 소속 변경 요청 흐름
엔드포인트: `POST /api/v1/account/affiliation`

흐름
1) 인증 확인
2) 입력 파싱 → `department`, `line`, `user_sdwt_prod`, `effective_from`
3) `Affiliation` 조합 유효성 검증
4) 기존 PENDING 요청 여부 검사
5) `UserSdwtProdChange` 생성 (status=PENDING)
6) 응답: 요청 상태 + changeId

관련 코드 경로
- `apps/api/api/account/views.py`
- `apps/api/api/account/services/affiliation_requests.py`
- `apps/api/api/account/selectors.py`

### 3) 승인/거절 흐름
엔드포인트: `POST /api/v1/account/affiliation/approve`

승인 흐름
1) change 조회
2) approver가 `to_user_sdwt_prod` 관리 권한이 있는지 확인
3) transaction:
   - User의 `user_sdwt_prod`, `department`, `line` 갱신
   - `affiliation_confirmed_at`, `requires_affiliation_reconfirm` 업데이트
   - Change 상태를 APPROVED로 기록
   - self-access 보장

거절 흐름
1) change 조회
2) 권한 확인
3) Change 상태를 REJECTED로 업데이트

관련 코드 경로
- `apps/api/api/account/services/affiliation_requests.py`

### 4) 승인 대기 목록 조회
엔드포인트: `GET /api/v1/account/affiliation/requests`

흐름
1) 요청자 권한 판별 (privileged vs manageable)
2) status/search/user_sdwt_prod 필터 적용
3) 페이지네이션 후 결과 반환

관련 코드 경로
- `apps/api/api/account/services/affiliation_requests.py`
- `apps/api/api/account/selectors.py`

### 5) 외부 예측 소속 재확인 흐름
엔드포인트
- `GET /api/v1/account/affiliation/reconfirm`
- `POST /api/v1/account/affiliation/reconfirm`

흐름
1) 외부 스냅샷(ExternalAffiliationSnapshot) 조회
2) 사용자가 수락하면 해당 값으로 소속 변경 요청 생성
3) 성공 시 `requires_affiliation_reconfirm` 초기화

관련 코드 경로
- `apps/api/api/account/services/affiliations.py`

### 6) 외부 스냅샷 동기화
엔드포인트: `POST /api/v1/account/external-affiliations/sync` (Airflow 토큰 전용)

흐름
1) records 업서트(ExternalAffiliationSnapshot)
2) 예측 소속이 바뀌면 `User.requires_affiliation_reconfirm = True`

관련 코드 경로
- `apps/api/api/account/services/external_sync.py`

## Emails

### 1) 핵심 모델
- `Email`: 수신 메일 저장 + RAG 연동 키 보유
- `EmailOutbox`: RAG 인덱싱/삭제 비동기 처리 큐

관련 코드 경로
- `apps/api/api/emails/models.py`

### 2) POP3 수집 → 저장 → RAG 등록
엔드포인트: `POST /api/v1/emails/ingest/`

흐름
1) POP3 접속 후 메시지 순회
2) 제목 제외 규칙(환경변수 `EMAIL_EXCLUDED_SUBJECT_PREFIXES`) 적용
3) 메일 파싱(수신자/본문/HTML 등)
4) 발신자(knox_id) 기준으로 소속 판별
5) Email 저장 (message_id 중복 방지)
6) 분류된 메일이면 RAG 인덱싱 Outbox 적재
7) POP3 메시지 삭제 커밋
8) 누락된 rag_doc_id 백필 시도

관련 코드 경로
- `apps/api/api/emails/services/ingest.py`
- `apps/api/api/emails/services/storage.py`
- `apps/api/api/emails/selectors.py`
- `apps/api/api/emails/services/rag.py`

### 3) 메일함/메일 조회
엔드포인트
- `GET /api/v1/emails/inbox/`
- `GET /api/v1/emails/sent/`
- `GET /api/v1/emails/mailboxes/`
- `GET /api/v1/emails/mailboxes/members/`

흐름 요약
1) `resolve_access_control`로 접근 가능 집합 계산
2) 메일함 목록:
   - privileged → 전체 known user_sdwt_prod + UNASSIGNED
   - 일반 사용자 → 접근 가능한 user_sdwt_prod
3) 메일 검색:
   - user_sdwt_prod 필터
   - 검색어/기간/발신자/수신자 필터 적용

관련 코드 경로
- `apps/api/api/emails/views.py`
- `apps/api/api/emails/selectors.py`
- `apps/api/api/emails/services/query_filters.py`

### 4) UNASSIGNED 메일 처리
엔드포인트
- `GET /api/v1/emails/unassigned/`
- `POST /api/v1/emails/unassigned/claim/`

흐름
1) sender_id(knox_id) 기준 UNASSIGNED 메일 수 집계
2) claim 요청 시:
   - 본인 `user_sdwt_prod`로 이동
   - classification_source=CONFIRMED_USER
   - rag_index_status=PENDING
   - RAG 인덱싱 Outbox 적재

관련 코드 경로
- `apps/api/api/emails/services/mutations.py`
- `apps/api/api/emails/selectors.py`

### 5) 메일 이동/삭제
엔드포인트
- `POST /api/v1/emails/move/`
- `POST /api/v1/emails/bulk-delete/`
- `DELETE /api/v1/emails/<email_id>/`

흐름
1) 권한 검사 후 메일 이동/삭제 수행
2) 이동 시:
   - user_sdwt_prod 갱신
   - RAG 인덱싱 Outbox 적재
3) 삭제 시:
   - RAG 삭제 Outbox 적재
   - Email 레코드 삭제

관련 코드 경로
- `apps/api/api/emails/services/mutations.py`
- `apps/api/api/emails/services/rag.py`

### 6) Outbox 처리
엔드포인트: `POST /api/v1/emails/outbox/process/`

흐름
1) PENDING Outbox 조회 후 PROCESSING으로 전환
2) INDEX → RAG insert
3) DELETE → RAG delete
4) 실패 시 retry/backoff, 최대 재시도 초과 시 FAILED

관련 코드 경로
- `apps/api/api/emails/services/rag.py`

### 7) 메일 발신 API
- 사내 Knox 메일 API 호출 기능 제공

관련 코드 경로
- `apps/api/api/emails/services/mail_api.py`

## RAG/Assistant

### 1) 설정/환경변수
핵심 설정
- `ASSISTANT_RAG_URL` / `RAG_SEARCH_URL`
- `ASSISTANT_RAG_INSERT_URL` / `RAG_INSERT_URL`
- `ASSISTANT_RAG_DELETE_URL` / `RAG_DELETE_URL`
- `RAG_INDEX_DEFAULT`, `RAG_INDEX_EMAILS`, `RAG_INDEX_LIST`
- `ASSISTANT_RAG_PERMISSION_GROUPS` / `RAG_PERMISSION_GROUPS`
- `RAG_PUBLIC_GROUP = rag-public`

관련 코드 경로
- `apps/api/api/rag/services/config.py`

### 2) RAG API Client 흐름
핵심 함수
- `search_rag`: 검색
- `insert_email_to_rag`: 이메일 인덱싱
- `delete_rag_doc`: 문서 삭제

흐름
1) 인덱스/permission_groups 정규화
2) payload 구성
3) 외부 RAG API 호출
4) 실패 시 파일 로그 기록

관련 코드 경로
- `apps/api/api/rag/services/client.py`
- `apps/api/api/rag/services/logging.py`

### 3) Email ↔ RAG 연동
흐름
1) Email 저장 후 RAG 인덱싱 Outbox 적재
2) Outbox 처리 시:
   - doc_id = `email-{id}`
   - permission_groups = [user_sdwt_prod, sender_id]
3) 삭제 시에도 동일 permission_groups로 delete 요청

관련 코드 경로
- `apps/api/api/emails/services/rag.py`
- `apps/api/api/rag/services/client.py`

### 4) Assistant ↔ RAG 연동
엔드포인트
- `GET /api/v1/assistant/rag-indexes`
- `POST /api/v1/assistant/chat`

흐름
1) permission_groups 결정/검증
2) RAG search 호출
3) 결과 contexts/sources 추출
4) LLM 호출 → 구조화 응답 파싱

관련 코드 경로
- `apps/api/api/assistant/views.py`
- `apps/api/api/assistant/services/chat.py`
- `apps/api/api/assistant/services/normalization.py`
