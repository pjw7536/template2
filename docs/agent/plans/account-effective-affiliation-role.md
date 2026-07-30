# ExecPlan: Account 현재 소속 실효 역할 통일

## 목표
- 현재 소속 사용자를 별도 `UserSdwtProdAccess` 행 없이도 해당 소속의 `member`로 일관되게 판정한다.
- `/settings/members`의 역할 표시, 승인 버튼, 승인·거절 API가 같은 권한 기준을 사용하게 한다.

## 현재 상태
- 멤버 목록과 Account 개요는 현재 소속에 권한 행이 없으면 `member`를 기본값으로 표시한다.
- 승인 요청 목록은 같은 사용자를 `viewer`로 직렬화하고, 승인·거절 서비스는 명시적 권한 행이 없으면 `403`을 반환한다.
- 현재 소속 사용자의 권한 행을 조회 시점에 자동 생성하지 않는 것이 기존 계약이다.

## 범위
- 수정할 영역: `api.account`의 소속 역할 판정, 승인 요청 직렬화, 승인·거절 권한 검사와 관련 테스트.
- 수정하지 않을 영역: Portal·앱 `UserAccess` 권한, DB schema, migration, frontend API 형태, 기존 공개 facade.

## 설계
- 공통 실효 소속 역할 판정 함수를 `services/utils.py`에 둔다.
- 명시적 `manager`를 최우선으로 유지하고, 대상이 현재 소속이면 최소 `member`를 반환한다.
- 다른 소속은 기존 `viewer/member/manager` 명시 권한만 인정한다.
- 승인 요청 응답의 `role`과 승인·거절 권한 검사가 동일한 판정 함수를 사용한다.
- API 응답 형태와 DB schema는 바뀌지 않으므로 migration은 생성하지 않는다.

## 실행 단계
- [x] 공통 실효 소속 역할 판정 함수 추가
- [x] 승인 요청 표시와 승인·거절 권한 검사에 공통 판정 적용
- [x] 현재 소속 무권한 행 member 및 다른 소속 viewer 경계 테스트 추가
- [x] 관련 Docker 테스트와 backend boundary audit 실행

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account.tests.AffiliationChangeApprovalTests api.account.tests.AffiliationChangeRequestListTests api.account.tests.AccountEndpointTests.test_account_affiliation_members_uses_account_domain`
- `npm run agent:audit:api-boundary`
- `git diff --check`

## 위험과 대응
- 위험: 현재 소속의 명시적 `viewer`가 승인 가능한 `member`로 승격될 수 있다.
- 대응: 현재 소속에는 `viewer`를 부여해도 `member`로 정규화하는 기존 서비스 계약과 맞춘다.
- 위험: 앱 접근 역할과 소속 역할이 섞일 수 있다.
- 대응: `UserAccess`와 scope 판정은 수정하지 않고 `UserSdwtProdAccess` 관련 서비스에만 변경을 제한한다.

## 진행 기록
- 2026-07-29: 현재 소속을 실효 `member`로 일관되게 인정하고 DB backfill 없이 판정 로직을 통일하기로 결정했다.
- 2026-07-29: 관련 회귀 테스트 11개와 account 전체 178개 테스트, backend boundary audit, `git diff --check`가 통과했다.
