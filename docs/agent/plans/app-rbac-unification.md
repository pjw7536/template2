# ExecPlan: 고정 역할 기반 접근 권한 단순화

## 목표
- Portal과 모든 앱이 동일한 `user`/`admin` 역할 계약을 사용한다.
- 사용자별 접근 상태와 역할은 `UserAccess` 한 행에서 관리한다.
- Portal admin은 전역 접근 승인·정책·감사 기능을 담당한다.
- 앱 admin은 해당 앱의 관리자 기능만 담당한다.
- 관리자 메뉴는 사용자가 보유한 Portal/앱 admin 역할에서 자동으로 구성한다.

## 시작 상태
- 미커밋 작업에 `AppRole`, `AppCapability`, `AppRoleCapability` 동적 RBAC 모델과 `access-control` 가상 앱이 추가되어 있다.
- Access Control은 코드 고정 capability를 사용하지만 AppStore와 L3 Spider는 DB 연결 capability를 사용하여 권한 규칙의 출처가 둘이다.
- 기존 Portal 일괄 승인과 Navbar Spider flyout 미커밋 변경은 보존해야 한다.
- `0005_app_rbac.py`는 아직 Git에 추적되지 않은 신규 migration이다.

## 추가 리뷰 기준
- 현재 운영 코드 기준점은 `6ccca29dc7901f59537d7be5a4aa654311692c1e`이다.
- 해당 커밋에는 account `0004`, L3 Spider `0007`, emails `0001`까지 포함되어 있고, 해당 커밋부터 현재 HEAD까지 추가된 migration은 없다.
- 서버에는 현재 워크트리의 account `0005`와 L3 Spider `0008` migration이 아직 적용되지 않았다.
- account `0005`는 Git에 추적되지 않은 신규 파일이므로 서버 최초 적용 전에 최종 release migration 형태로 정리할 수 있다.
- 로컬 개발 DB에는 account `0005`가 적용되어 있으므로 migration 파일을 정리하기 전에 백업 후 로컬 DB를 `0004` 기준으로 재구성하거나 새 개발 DB로 교체해야 한다.
- emails `0001_initial.py`는 기존부터 추적된 migration이므로 현재 워크트리에서 추가한 `TrigramExtension` 작업은 서버 미적용 전제에 포함되지 않는다.
- 추가 리뷰에서 승인·부여 사유 유실, 앱별 관리자 권한 출처 불일치, 비-Portal 사용자 필터의 전체 메모리 계산, 정책 URL별 HTTP method 누수, 중복 API 필드와 legacy 감사 snapshot, 요청 resolver 중복 조회를 확인했다.

## 범위
- account 접근 모델, selector, service, API, Admin, 테스트를 고정 역할 계약으로 단순화한다.
- AppStore와 L3 Spider의 관리자 검사를 앱 `admin` 역할 검사로 전환한다.
- Portal 관리자 메뉴와 권한 관리 화면을 Portal `admin` 역할에 연결한다.
- 기존 Portal 일괄 승인과 Spider flyout 동작은 유지한다.
- 소속 역할, 리소스 소유권, L3 mail rule의 owner/read/write 권한은 변경하지 않는다.

## 설계
- `AccessRole`은 `user`와 `admin` 두 값만 가진다.
- 역할은 `UserAccess.role` 한 컬럼에만 저장한다.
- `(user, scope)` 유일 제약과 role DB check를 유지한다.
- 접근 요청, 부서 자동 정책, 일괄 승인의 역할은 코드에서 `user`로 고정한다.
- 부서 자동 정책 및 Portal 일괄 승인은 `user`만 자동 부여하며 `admin`은 명시적으로만 부여한다.
- Portal `admin`은 접근 현황 조회, 승인·차단, 정책 관리, 감사 조회 권한을 가진다.
- 앱 `admin`은 해당 앱의 관리 기능을 가진다.
- 일반 운영 권한은 `has_scope_role(user, scope_key, role=admin)` 공통 서비스에서 판정한다.
- 요청 생명주기 안에서는 scope/접근 판정 결과를 재사용해 같은 역할 검사가 반복 쿼리를 만들지 않게 한다.
- 런타임 접근 판정과 사용자 목록의 DB 필터 판정은 구현 형태가 달라도 동일한 상태·출처 결과를 내야 하며, 대표 상태 전체를 비교하는 계약 테스트로 동등성을 고정한다.
- `is_superuser`는 기존처럼 모든 접근·역할 검사를 우회하는 비상 운영 권한으로 유지한다.
- `is_superuser`의 유효 권한은 명시 접근 행으로 바꿀 수 없으므로 모든 사용자 권한 mutation은
  대상 사용자를 잠근 뒤 `409 immutable_access_bypass`로 거절하고 감사 로그도 남기지 않는다.
- auth payload는 일반 사용자에게 Portal과 모든 활성 scope를, 비상 운영 권한인
  `is_superuser`에게는 비활성 scope까지 포함하는 단일 `scope_access` map을 반환한다.
- 접근 신청은 `/access/request`, 관리 결정은 `/access/users/<user_id>/decision`만 사용한다.
- `portal_access`, `app_access`, 요청 ID 기반 Portal 승인 API와 legacy 입력 별칭은 제거한다.
- 관리자 메뉴 그룹은 Portal 또는 앱의 `admin` 역할로 접근 가능한 하위 항목이 하나 이상일 때만 표시한다.
- 동적 역할/capability 모델과 `access-control` 가상 scope는 제거한다.
- 신규 단일 migration은 legacy 사용자 역할을 `user/admin`으로 정규화하고 중복 역할 컬럼과 legacy 관리 그룹을 제거한다.
- Portal 이외의 모든 scope 유형은 Portal 접근을 공통 선행 조건으로 사용한다. `feature` 유형도 같은 규칙을 적용해 새 scope 유형의 우회 가능성을 막는다.
- 별도 소비처가 없는 사용자 프로필 운영 역할과 자동 생성 체인은 제거하고 접근 역할은 `UserAccess.role`만 사용한다.
- 권한 결정 API와 mutation service는 사용자+scope 기반 canonical 경로 하나만 유지한다.
- `pending`·`denied` 접근 행은 항상 `user` 역할만 저장하고, `admin`은 `allowed` 행에만 저장한다.
- `grant`·`approve`가 역할을 생략하면 기존 역할을 재사용하지 않고 `user`를 사용한다.
- AppStore serializer는 권한을 직접 조회하지 않고 요청 경계에서 한 번 계산한 관리자 여부만 받는다.

### Migration 최종화
- 서버에 아직 배포되지 않았던 초기 account `0005`~`0007` draft는 하나의 최종 `0005_fixed_access_roles` migration으로 정리한다.
- account `0005`는 기존 role 정규화, `default_role`·정책 `role`·미사용 `UserProfile` 제거, 비허용 행의 `user` 역할 강제, DB check constraint, legacy 접근 감사 기록 정규화를 수행한다.
- 같은 migration에서 scope key·Portal 식별자 제약과 감사 참조 `PROTECT`까지 최종 스키마를 한 번에 적용한다.
- 감사 로그 정규화는 schema 변경 잠금을 잡기 전에 실행하고, 실제 변경된 행만 batch 갱신해 운영 로그 수에 따른 배포 잠금 시간을 줄인다.
- 기존 `UserAccess`의 허용·대기·차단 상태와 요청·결정 시각은 유지하고 역할만 `user`로 정규화한다.
- 소속, affiliation 역할, 일반 Django group/permission과 앱 데이터는 변경하지 않고 legacy 접근 관리자 group/permission과 L3 개발자 permission만 제거한다.
- 운영에 최초 적용한 뒤의 추가 스키마 변경은 기존 `0005`를 수정하지 않고 새 번호 migration으로 처리한다.
- 이미 추적된 emails `0001_initial.py`의 `TrigramExtension` 추가는 되돌린다.
- 개발·테스트의 `pg_trgm`은 기존 `ensure_dev_database`가 개발 DB와 테스트 DB 생성 원본에 확장을 준비하도록 보강하고, 운영 신규 DB는 migration 전 필수 extension으로 문서화한다.

### Canonical API 계약
- 접근 payload는 `allowed`, `scope`, `scopeType`, `role`, `explicitStatus`, `effectiveStatus`, `source`, `reason`, `canRequest`, 시각·거절 사유, `policy`, Portal 차단 정보만 반환한다.
- 정확히 중복되는 `status`, `policyMatched`, `departmentAllowed`는 제거하고 프론트엔드·fixture·문서·테스트를 동시에 변경한다.
- 감사 API의 `before`·`after`는 action별 canonical snapshot만 반환하고 과거 `defaultRole`, 정책 `role`, `canManageAccess`를 응답 시점에 다시 노출하지 않는다.
- 접근 신청은 `/account/access/request`, 관리 결정은 `/account/access/users/<user_id>/decision`만 유지한다.
- Portal이 필요한 앱 접근 신청은 같은 transaction에서 Portal pending과 앱 pending을 함께 생성해 부분 성공을 없앤다.
- query parameter는 전용 serializer에서 camelCase 이름과 허용 값·범위를 엄격히 검증하고 잘못된 값은 `400 invalid_query`로 반환한다.
- 정책 규칙 목록/생성 View와 상세 수정/삭제 View를 분리해 지원하지 않는 HTTP method는 `405`로 반환한다.
- 사용하지 않는 사용자 목록 `summary`는 제거하고 전체 건수는 `pagination.total` 한 곳에서만 제공한다.
- 감사 로그의 `scope=all`, `action=all`은 모두 필터 없음이라는 같은 계약으로 처리한다.

### Canonical 변경 경로
- `UserAccess`와 `AccessPolicyRule` 쓰기는 Portal 권한 관리 API만 사용하고 Django Admin에서는 읽기 전용으로 제공한다.
- Django Admin에 남는 `AccessScope` 쓰기는 account service의 canonical 감사 로그 writer만 사용한다.
- 감사 snapshot은 release migration에서 과거 데이터까지 정규화하고, 저장·조회 런타임은 action별 canonical 필드만 처리한다.
- 활동 로그와 권한 관리 응답은 저장소 내부 소비자가 없는 `isStaff`와 조직 중복 필드를 노출하지 않는다.
- `/auth/me`는 실제 접근 판정에 쓰는 `is_superuser`와 `scope_access`만 유지하고 빈 `roles`와 Django Admin용 `is_staff`는 노출하지 않는다.

### 권한 판정과 성능
- Portal admin 확인도 공통 permission이 만든 request-scoped resolver를 재사용하며 service가 별도 scope·정책·UserAccess 조회를 다시 만들지 않는다.
- 비-Portal scope의 상태·출처 필터는 selector의 annotation/`Exists`/`Case` 표현으로 DB에서 계산한 뒤 페이지네이션한다.
- 사용자 수가 증가해도 목록 API의 query 수는 고정되고 Python 메모리 사용량은 page size에 비례해야 한다.
- AppStore serializer의 관리자 boolean 주입과 L3 Spider permission의 request cache 재사용은 유지한다.
- 런타임 접근 판정·직렬화는 읽기 전용 `access_runtime` 서비스로 분리하고,
  접근 신청·관리 결정·정책·감사 쓰기는 `access_control`에 유지해 상태 변경 경계를 명확히 한다.
- 프론트 권한 관리 화면은 페이지가 데이터 조합과 mutation을 담당하고,
  요약·결정 dialog·대기 요청·정책·감사 패널은 책임별 컴포넌트로 분리한다.
- 책임 분리 전후의 public service facade, API payload, query ceiling과 화면 동작은 변경하지 않는다.
- 접근 신청 HTTP 호출은 account API client 한 곳에서 수행하고 Portal/App gate는 같은
  canonical `scopes` 요청 함수를 사용한다.
- query의 `all` sentinel 정규화는 serializer에서 한 번만 수행하며, DB 필터 이후의
  사용하지 않는 Python status/source 재필터와 불변조건을 숨기는 빈 객체 fallback은 제거한다.
- `services` facade는 읽기 전용 접근 판정을 `access_runtime`에서 직접 export하고
  mutation 모듈을 단순 재-export 경로로 사용하지 않는다.
- 저장소 내부 소비자가 없는 소속 권한 단건 변경·별도 관리 목록 API와 frontend hook을
  제거하고, 관리 가능 소속 목록은 account overview 응답만 사용한다.
- 초기 권한 명령과 함께 생산자가 사라진 `user_access_update` 감사 action을 현재 모델과
  미적용 migration, UI 라벨에서 제거한다.
- 감사 snapshot은 migration과 쓰기 경계에서만 정규화하고 조회 시 재정규화하지 않는다.

### 앱 관리자 통일
- 앱 전체에 영향을 주는 관리 기능은 모두 해당 `scope`의 `admin` 역할을 유일한 일반 사용자 권한으로 사용한다.
- VOC 게시판 관리, Emails 전체·UNASSIGNED 메일함 관리, Access Stats 수동 반영·동기화, Line Dashboard의 Drone Target 관리 기능을 각각 `voc`, `emails`, `access-stats`, `line-dashboard` admin으로 전환한다.
- `is_staff`는 Django Admin 로그인 용도로만 사용하고 앱 관리자 우회에는 사용하지 않는다.
- `is_superuser`는 최초 Portal admin 지정과 장애 대응을 위한 최종 우회 권한으로 유지한다.
- 게시글 작성자, 메일함 소속, 알림 대상 소유자 같은 리소스별 권한은 scope admin과 별도로 유지한다.
- `UserProfile`은 런타임·API·소속 업무 소비처가 없으므로 모델, signal, service, selector, Django Admin과 함께 제거한다.
- 프론트엔드는 `scope_access`의 `role=admin`만 사용해 관리자 제어와 route를 표시한다.
- Admin 메뉴에는 실제 관리 화면이 있는 scope만 `adminScope` 항목으로 등록하고, 별도 관리 화면이 없는 앱은 기존 앱 화면 안에서 admin 제어만 노출한다.

### Scope 수명주기와 확장성 고정
- `AccessScope`는 런타임에서 임의 생성하는 설정값이 아니라 코드·migration과 함께 배포하는 고정 권한 식별자 목록으로 취급한다.
- 신규 scope 생성은 migration으로만 허용하고 Django Admin에서는 추가·삭제를 모두 금지한다.
- 생성된 scope의 `key`와 `scope_type`은 변경하지 않으며, 사용 중단은 물리 삭제 대신 `is_active=False`로 표현한다.
- scope key는 소문자 영숫자와 단일 하이픈 구분 형식만 허용한다.
- canonical Portal은 `key=portal`과 `scope_type=portal`이 서로를 항상 함의하도록 DB check constraint로 고정한다.
- 권한 매트릭스는 Portal과 모든 활성 비-Portal scope를 표시하고 `app`·`feature`를 같은 변경 API로 관리한다.
- Portal 승인 시 일괄 부여하는 대상은 기존 계약대로 활성 `app` scope에만 제한한다.
- 대기 요청 화면은 명시적인 scope 선택값을 사용해 app·feature 요청을 같은 화면에서 처리한다.
- 사용자와 scope는 물리 삭제하지 않고 비활성화하며, 감사 로그의 scope·작업자·대상 사용자 FK는 `PROTECT`로 보존한다.
- 초기 권한 일괄 부여는 제공하지 않으며 최초 Portal 관리자는 지정한 Django superuser가 명시적으로 부여한다.
- 배포 무결성 명령은 필수 `--phase=pre-migration|post-migration` 인자로 실행 시점을 고정한다.
  전자는 `0004`의 legacy 역할 계약을, 후자는 최종 `user/admin` 역할·상태 계약을 검사한다.
- 운영 API entrypoint는 migration을 자동 실행하지 않으며, 배포 중 API를 중지한 상태에서 같은 release image의 one-off 명령으로 migration과 전후 무결성 검사를 실행한다.

## 실행 단계
- [x] 모델과 migration을 `UserAccess.role` 중심 구조로 단순화한다.
- [x] selector/service/API/Admin을 고정 역할 검사로 전환한다.
- [x] AppStore와 L3 Spider 관리자 권한을 앱 admin 역할로 전환한다.
- [x] auth payload와 권한 관리 UI를 문자열 역할 계약으로 전환한다.
- [x] Portal 관리자 메뉴를 역할 기반으로 구성한다.
- [x] 관련 테스트를 고정 역할 계약으로 갱신한다.
- [x] migration, backend, frontend, boundary 검증을 실행한다.
- [x] Appstore 관리자 판정을 요청당 한 번만 수행하고 쿼리 수 회귀 테스트를 추가한다.
- [x] 권한 관리 화면의 Portal 일괄 앱 승인을 통합 사용자 결정 API에 연결한다.
- [x] 기존 `UserAccess` 역할을 전부 `user`로 정규화하고 legacy L3 개발자 permission을 제거한다.
- [x] legacy 권한 관리자 감사 기록을 Portal 고정 역할 계약으로 정규화한다.
- [x] 권한 매트릭스의 순환 클릭을 명시적 `user`/`admin`/차단 선택 메뉴로 바꾼다.
- [x] 변경된 API, migration, 권한 UI를 다시 통합 검증한다.
- [x] 권한 매트릭스에서 미설정·대기·차단·허용 역할을 명시적으로 구분한다.
- [x] 두 권한 결정 API가 하나의 canonical mutation service를 사용하도록 통합한다.
- [x] 요청 단위 역할 판정 캐시를 추가하고 Portal 이외 모든 scope의 Portal 선행 조건을 일관되게 적용한다.
- [x] 최종 소비처 감사 후 `UserProfile`과 남은 생성·조회 체인을 미적용 `0005` migration에서 제거한다.
- [x] `MigrationExecutor`로 `0004`에서 `0005`까지의 실제 과거 상태 migration을 검증한다.
- [x] 전체 backend/frontend/migration/boundary 검증을 다시 실행한다.
- [x] 비허용 상태의 `admin` 저장을 서비스와 DB 제약조건에서 차단한다.
- [x] AppStore serializer의 암묵적 권한 조회 fallback을 제거한다.
- [x] 관리자 역할 재활성화와 AppStore 고정 권한 조회 회귀 테스트를 추가한다.
- [x] 후속 migration, backend, boundary 검증을 실행한다.
- [x] auth 응답을 Portal 포함 `scope_access` 단일 계약으로 전환한다.
- [x] 프론트 권한 조회와 접근 신청을 canonical scope 계약으로 전환한다.
- [x] 요청 ID 기반 Portal 승인 API와 legacy 입력·응답 별칭을 제거한다.
- [x] 가상 `defaultRole`, 정책 `role`, `canManage`, 프로필 응답 별칭을 제거한다.
- [x] 개발 fixture와 현재 API 문서를 고정 역할 계약에 맞춘다.
- [x] offsite auth wiring, migration drift, 전체 회귀와 경계 감사를 다시 실행한다.
- [x] 운영 코드 기준 커밋에서 account `0004`, L3 Spider `0007`, 기존 emails `0001`이 마지막 migration임을 확인한다.
- [ ] 배포 직전 운영 DB의 실제 migration ledger가 코드 기준과 같은지 읽기 전용으로 확인한다.
- [x] 로컬 개발 DB를 백업하고 최종 account schema와 migration ledger를 안전하게 일치시킨다.
- [x] account `0005`~`0007`을 데이터 보존형 단일 release migration으로 정리하고 `0004 → 0005` 역사 테스트를 갱신한다.
- [x] emails `0001_initial.py`를 원복하고 개발·테스트·운영의 `pg_trgm` 선행 조건을 bootstrap과 문서로 고정한다.
- [x] 승인·부여·역할 변경 사유를 `AccessAuditLog.reason`에 보존하고 일괄 앱 부여 감사에도 같은 사유를 전달한다.
- [x] 접근 payload와 감사 snapshot을 canonical 계약으로 줄이고 legacy 필드·action 정규화를 완료한다.
- [x] 접근 신청을 transaction 단위 Portal+앱 원자 처리로 바꾸고 중복·부분 성공 회귀 테스트를 추가한다.
- [x] 접근 관리 query serializer를 추가하고 정책 collection/detail View를 분리한다.
- [x] 비-Portal 상태·출처 필터를 DB 계산과 선페이지네이션 구조로 변경하고 대량 사용자 회귀 테스트를 추가한다.
- [x] Portal admin 검사에서 request-scoped resolver를 재사용하고 endpoint query ceiling 테스트를 추가한다.
- [x] VOC, Emails, Access Stats, Line Dashboard의 앱 전체 관리자 기능을 scope admin으로 전환한다.
- [x] 관리자 route·메뉴·화면 제어를 `scope_access` 단일 계약으로 전환하고 `is_staff`·legacy role 프론트 판정을 제거한다.
- [x] 현재 API·모듈 문서를 갱신하고 과거 권한 ExecPlan에는 현재 계획으로 대체됐다는 표시를 추가한다.
- [x] fresh DB, `0004 → 0005` 데이터 migration, backend 전체 회귀, frontend lint/build, 경계·문서 감사를 실행한다.
- [x] 감사 로그 migration을 schema 변경 전 batch 갱신으로 최적화한다.
- [x] Django Admin의 사용자 접근·정책 쓰기를 제거하고 scope 감사 기록을 canonical writer로 통일한다.
- [x] 공백 부서 DB 필터와 감사 `action=all` 계약을 수정한다.
- [x] 이전 superuser/staff 전용 설명을 scope admin 계약으로 정리한다.
- [x] 보완 회귀 테스트와 전체 검증을 완료한다.
- [x] scope key/type 불변, 생성·삭제 금지와 Portal 유일성 DB 제약을 추가한다.
- [x] 감사 로그 참조를 `PROTECT`로 바꾸고 사용자 물리 삭제를 비활성화 정책으로 전환한다.
- [x] Portal·app·feature를 같은 권한 매트릭스와 대기 요청 화면에서 관리한다.
- [x] scope 수명주기·feature 관리·감사 보존 회귀 테스트와 전체 검증을 완료한다.
- [x] 런타임 접근 판정과 DB 상태·출처 필터의 동등성 계약 테스트를 추가한다.
- [x] Emails Knox ID와 Access Stats 관리자 계약 설명을 실제 동작에 맞춘다.
- [x] 후속 migration과 권한 계약 회귀를 전체 검증한다.
- [x] 배포 무결성 검사를 migration 전·후 계약으로 분리하고 운영 절차를 갱신한다.
- [x] 슈퍼유저 대상 권한 mutation을 공통 잠금 경계에서 차단하고 무기록 회귀 테스트를 추가한다.
- [x] 운영 API 시작에서 migration을 분리하고 one-off 배포 절차로 문서를 통일한다.
- [x] 초기 권한 일괄 부여 명령과 전용 상태 모델·marker 승계·테스트·문서를 제거한다.
- [x] 미사용 소속 권한 API·frontend hook·facade와 zero-reference selector를 제거한다.
- [x] 감사 action 잔존 코드와 조회 재정규화, middleware 권한 판정 중복을 제거한다.
- [x] dead-code 정리 후 backend/frontend·migration·boundary·문서 검증을 완료한다.
- [x] 저장소 내부 미사용 권한 응답 필드와 프론트 전달값을 제거한다.
- [x] 감사 snapshot의 런타임 legacy fallback을 제거하고 scope payload 계산을 resolver 하나로 통합한다.
- [x] 정리 후 관련 backend/frontend·migration drift·boundary 검증을 완료한다.
- [x] 운영 역할과 소속 역할을 섞던 계정 개요 fallback을 제거한다.
- [x] Emails sender ID 정규화와 내부 helper 공개 표면을 하나로 정리한다.
- [x] 추가 정리 후 관련 backend/frontend·migration drift·boundary 검증을 완료한다.
- [x] 런타임 접근 판정과 상태 변경 서비스를 책임별 모듈로 분리한다.
- [x] 권한 관리 화면의 요약·결정·대기 요청·정책·감사 UI를 책임별 컴포넌트로 분리한다.
- [x] AccessScope Admin의 실질 변경 없는 저장은 감사 로그를 남기지 않도록 회귀 테스트로 고정한다.
- [x] 책임 분리 후 backend/frontend 전체 회귀와 경계 감사를 다시 실행한다.
- [x] canonical 접근 신청 client와 scope 요구사항 resolver의 중복 구현을 통합한다.
- [x] query 정규화·접근 목록 재필터·request fallback의 중복과 불필요 경로를 제거한다.
- [x] 단일 서비스 test patch loop와 권한 화면 scope 목록의 이중 source fallback을 제거한다.
- [x] 호환성 정리 후 backend/frontend 전체 회귀와 경계 감사를 다시 실행한다.
- [x] 부서 정책의 런타임 판정·목록 필터·무결성 검사가 PostgreSQL `Lower`가 계산한 같은 정규화 값을 사용하도록 통일한다.
- [x] `İ`/`I`와 Greek sigma처럼 Python·PostgreSQL 결과가 다른 부서명으로 런타임·DB 필터 동등성 회귀를 검증한다.
- [ ] 운영 DB 복제본에서 migration과 일반 사용자·앱 admin·Portal admin smoke test를 완료한 뒤 배포한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py showmigrations account l3_spider emails`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.auth api.appstore api.l3_spider api.voc api.emails api.activity api.drone`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration`
- `npm --prefix apps/web run lint`
- `npm --prefix apps/web run build`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `scripts/agent/check_docs_inventory.sh`
- `git diff --check`

### 필수 검증 시나리오
- account `0004` 상태의 사용자·소속·접근 요청·정책·감사 데이터를 만든 뒤 최종 `0005`를 적용해 비접근 데이터가 그대로 유지되는지 확인한다.
- 새 빈 DB에서 전체 migration을 처음부터 실행해 `pg_trgm`, emails trigram index와 account schema가 정상 생성되는지 확인한다.
- 일반 사용자, 앱 `admin`, Portal `admin`, superuser가 각자 허용된 API만 호출할 수 있는지 앱별로 확인한다.
- 승인·직접 부여·역할 변경·차단·정책 복귀·일괄 앱 승인 감사 로그의 action, before, after, reason이 canonical 형태인지 확인한다.
- 잘못된 page/pageSize/status/source/userId/action과 잘못된 정책 URL method가 각각 `400` 또는 `405`를 반환하는지 확인한다.
- 대량 사용자 fixture에서 페이지 크기보다 많은 사용자 객체를 Python에 적재하지 않고 query 수가 사용자 수와 무관하게 고정되는지 확인한다.
- 금지된 계약 문자열 `portal_access`, `app_access`, `defaultRole`, `canManageAccess`, `policyMatched`가 현재 코드·fixture·API 문서에 남지 않았는지 검색한다.
- canonical Portal 이외의 `portal` 유형 scope와 잘못된 key 형식이 DB 제약조건에서 거절되는지 확인한다.
- scope key/type 변경과 scope·사용자 물리 삭제가 거절되고 비활성화는 정상 동작하는지 확인한다.
- 활성 feature scope가 권한 매트릭스·대기 요청·정책·감사 화면에서 app과 같은 방식으로 관리되는지 확인한다.
- 배포 migration이 일반 사용자의 권한 행을 새로 만들거나 기존 결정을 덮어쓰지 않는지 확인한다.

## 위험과 대응
- 위험: 서버에는 미적용이어도 로컬 개발 DB에 적용된 account `0005`를 바로 편집하면 로컬 migration history와 파일이 어긋날 수 있다.
- 대응: 파일 정리 전에 로컬 DB를 백업하고 `0004` 기준의 새 개발 DB에서 최종 migration을 검증한다. 기존 로컬 DB는 자동 삭제하지 않는다.
- 위험: 운영 기준 커밋 이후 현재 HEAD까지 RBAC 이외의 Drone, L3 Spider, Line Dashboard 변경 커밋 4개도 함께 배포될 수 있다.
- 대응: 배포 후보 SHA와 `6ccca29d..배포후보` diff를 확인하고, RBAC만 별도 배포하려면 release branch에서 포함 커밋을 명시적으로 구성한다.
- 위험: 기존 emails `0001`을 수정하면 이미 적용된 서버와 신규 DB의 실행 경로가 달라진다.
- 대응: tracked migration을 원복하고 `pg_trgm`을 DB bootstrap 선행 조건으로 분리한다.
- 위험: 앱 관리자 전환에서 기존 `is_staff` 사용자의 앱 전체 관리 권한이 사라질 수 있다.
- 대응: 사용자 확인대로 기존 앱 관리자 권한 보유자는 없다는 전제로 자동 승계하지 않으며, 비관리 소속·리소스 권한은 별도 회귀 테스트로 보존한다.
- 위험: Portal+앱 원자 신청이 동일 scope 중복 요청이나 명시 차단 상태를 잘못 덮을 수 있다.
- 대응: scope별 row를 transaction 안에서 잠그고 pending은 idempotent하게 유지하며 명시 차단의 재신청 규칙을 service 테스트로 고정한다.
- 위험: API 중복 필드 제거가 저장소 내부 호출자를 깨뜨릴 수 있다.
- 대응: backend serializer, frontend reader, dev fixture, 테스트와 문서를 한 변경에서 전환하고 legacy fallback을 남기지 않는다.
- 위험: DB 계산 필터가 Python 판정과 달라질 수 있다.
- 대응: 동일 사용자 집합에 대해 기존 판정 함수와 DB annotation 결과를 비교하는 selector 회귀 테스트를 추가한다.
- 위험: Python `casefold()`와 PostgreSQL `lower()`의 Unicode 결과 차이로 auth 접근 판정과 관리 목록 필터가 서로 다른 사용자를 반환할 수 있다.
- 대응: 이미 DB 제약과 목록 필터가 사용하는 `lower()`를 canonical 계약으로 정하고 런타임·무결성 검사도 같은 규칙으로 맞춘 뒤 Unicode 회귀 테스트로 고정한다.
- 위험: migration 이후 구버전 애플리케이션으로만 되돌리면 제거·rename된 컬럼 때문에 실행되지 않을 수 있다.
- 대응: 배포 전 DB 백업과 운영 복제본 검증을 필수화하고, 실패 시 migration reverse보다 구버전 코드와 DB 백업을 함께 복원한다.
- 위험: schema 변경 후 감사 로그 전체를 개별 저장하면 DDL 잠금이 운영 로그 수만큼 길어질 수 있다.
- 대응: 감사 로그를 DDL보다 먼저 canonical 형태로 계산하고 변경 행만 batch 갱신한다.
- 위험: Django Admin과 Portal API가 서로 다른 snapshot 형식과 상태 전이 규칙을 만들 수 있다.
- 대응: 사용자 접근·정책은 Portal API를 유일한 쓰기 경로로 만들고 scope Admin만 공통 감사 writer를 사용한다.
- 위험: 기존 역할 문자열을 새 `admin`으로 자동 승격하면 의도하지 않은 관리자가 생길 수 있다.
- 대응: 사용자가 기존 관리자·L3 개발자 권한 보유자가 없음을 확인했으므로 모든 기존 `UserAccess` 역할을 `user`로 정규화하고 관리자는 migration 이후 명시적으로만 부여한다.
- 위험: Portal admin과 앱 admin이 서로의 권한을 과도하게 상속할 수 있다.
- 대응: Portal admin은 전역 접근 관리에만, 앱 admin은 해당 앱 관리자 기능에만 사용한다.
- 위험: 메뉴만 숨기고 API가 열려 있을 수 있다.
- 대응: 모든 관리자 API에서 공통 backend 역할 검사를 수행하고 UI는 같은 payload를 표시용으로만 사용한다.
- 위험: 기존 미커밋 Portal 일괄 승인과 Spider flyout 변경을 잃을 수 있다.
- 대응: 두 흐름의 diff와 테스트를 유지한 채 RBAC 관련 코드만 교체한다.
- 위험: 최초 Portal admin이 없으면 일반 운영자가 권한을 관리할 수 없다.
- 대응: Django superuser 우회를 유지해 최초 Portal admin을 지정할 수 있게 한다.
- 위험: superuser의 명시 접근 행을 변경해도 실제 우회 권한은 바뀌지 않아 화면과 감사 로그가 실제 권한과 달라질 수 있다.
- 대응: 사용자 권한 mutation의 공통 transaction에서 대상을 먼저 잠그고 superuser면 쓰기 전에 일관된 충돌 응답으로 중단한다.
- 위험: API 컨테이너마다 시작 시 migration을 실행하면 여러 인스턴스 배포에서 migration과 애플리케이션 시작이 섞일 수 있다.
- 대응: 운영 entrypoint에서는 migration을 제거하고 API 중지 구간에 같은 release image의 one-off 명령으로 한 번만 실행한다.
- 위험: 신버전 무결성 명령을 legacy schema에 실행하면 정상 legacy 역할을 오류로 보고하거나 아직 없는 테이블을 조회할 수 있다.
- 대응: 실행 phase를 필수 인자로 받고 migration 전·후 역할 계약과 운영 row-count 절차를 명시적으로 분리한다.
- 위험: 권한 표에서 자동 거절과 명시적 차단을 같은 값으로 표시하면 사용자가 차단을 선택해도 DB에 기록되지 않을 수 있다.
- 대응: `explicitStatus`를 선택값의 기준으로 사용하고 미설정·대기 상태를 별도 읽기 상태로 표시한다.
- 위험: 접근 판정 helper를 분리하면서 request-scoped resolver 재사용이나 DB 판정 동등성이 깨질 수 있다.
- 대응: 기존 public facade를 유지하고 접근 상태 계약·query ceiling·selector 동등성 테스트를 그대로 실행한다.
- 위험: Django Admin에서 변경이 없는 저장까지 감사 로그가 쌓이면 실제 운영 변경 이력이 노이즈에 묻힐 수 있다.
- 대응: canonical before/after snapshot이 다른 경우에만 `scope_update`를 기록하고 no-op 저장 회귀 테스트를 추가한다.
- 위험: 사용하지 않는 `UserProfile` 테이블 제거가 외부 DB 직접 조회 작업을 깨뜨릴 수 있다.
- 대응: 저장소 내부 소비처가 없고 독립 운영 용도가 없다는 사용자 확인을 기준으로 제거하며, 운영 배포 전 외부 DB 의존성을 점검한다.
- 위험: 프로세스 전역 캐시는 권한 변경 직후 오래된 결과를 반환할 수 있다.
- 대응: 전역 캐시를 사용하지 않고 요청 객체에만 제한된 캐시를 둔다.
- 위험: 차단된 행에 남은 `admin` 역할이 역할 없는 재허용에서 다시 활성화될 수 있다.
- 대응: 비허용 행은 `user`로 정규화하고 조건부 DB check와 canonical service에서 같은 규칙을 강제한다.
- 위험: AppStore serializer의 선택적 관리자 인자를 누락하면 항목별 권한 조회가 재발할 수 있다.
- 대응: 관리자 여부를 필수 keyword 인자로 바꾸고 serializer와 순수 소유권 판정 함수에서 DB 조회 fallback을 제거한다.
- 위험: 구형 외부 클라이언트가 `portal_access`, `app_access` 또는 `/portal-access/approvals`를 계속 호출할 수 있다.
- 대응: 사용자의 명시적 계약 통일 요청에 따라 호환 계층을 종료하고 저장소 내부 호출자·테스트·문서를 같은 변경에서 모두 전환한다.
- 위험: 과거 감사 로그에는 제거된 `role`, `defaultRole`, `canManageAccess` snapshot이 남을 수 있다.
- 대응: 최종 release migration에서 과거 snapshot을 canonical 형태로 정규화하고 API serializer와 감사 화면도 canonical 필드만 사용한다.
- 위험: 이미 생성된 비정상 scope가 새 Portal/key 제약조건 적용을 막을 수 있다.
- 대응: migration 전 데이터 검증에서 비정상 행을 명시적으로 보고하고 자동 의미 변경 없이 배포를 중단한다.
- 위험: 사용자 물리 삭제를 막으면 기존 운영 절차가 삭제 오류를 만날 수 있다.
- 대응: Django Admin의 삭제 동작을 제거하고 `is_active=False`를 유일한 운영 비활성화 절차로 문서화한다.
- 위험: feature scope를 매트릭스에 포함하면 Portal 승인 일괄 부여 범위까지 넓어질 수 있다.
- 대응: 매트릭스 조회는 모든 활성 scope를 사용하되 일괄 부여 selector는 활성 app 전용으로 유지한다.
- 위험: 문서화되지 않은 응답 필드를 외부 호출자가 사용하고 있을 수 있다.
- 대응: 현재 RBAC 변경에서 새로 생겼거나 저장소 내부 미사용이 확인된 필드만 제거하고, Appstore와 Activity 입력 alias처럼 외부 소비 여부가 불명확한 기존 계약은 유지한다.

## 진행 기록
- 2026-07-28: 정책 값과 사용자 부서를 기존 조회에서 PostgreSQL `Lower` annotation으로 함께 계산하고 Python fallback을 제거했다. `İ`/`I` 허용과 `ΟΣ`/`ος` 불일치 계약을 추가했으며 집중 3 tests, account 156 tests, backend 전체 832 tests, migration drift, backend boundary, 문서 inventory, diff 검증을 통과했다.
- 2026-07-28: 재리뷰에서 Python `lower()`도 PostgreSQL `Lower`와 `İ` 및 Greek final sigma 결과가 다름을 실제 DB에서 재현했다. 스키마 변경 없이 기존 policy/user 조회에 DB 정규화 annotation을 포함해 판정 원본을 PostgreSQL로 단일화하기로 했다.
- 2026-07-28: 부서 정책 런타임 판정과 무결성 검사를 PostgreSQL `Lower` 계약에 맞추고 `Straße`/`STRASSE` 회귀를 추가했다. 집중 3 tests와 account 156 tests, migration drift, backend boundary, 문서 inventory, diff 검증을 통과했다.
- 2026-07-28: 코드 리뷰에서 Python `casefold()`와 PostgreSQL `lower()`의 Unicode 정규화 차이로 런타임 접근 판정·관리 목록 필터·무결성 검사가 불일치할 수 있음을 확인하고 `lower()` 계약으로 통일하기로 했다.
- 2026-07-27: 운영 기준 커밋이 `6ccca29dc7901f59537d7be5a4aa654311692c1e`임을 확인했다. 이 커밋의 마지막 migration은 account `0004`, L3 Spider `0007`, emails `0001`이며 현재 HEAD까지 추가된 migration은 없다.
- 2026-07-27: 운영 기준 이후 현재 HEAD에는 migration 없는 별도 기능 커밋 4개가 있으므로 배포 후보 전체 diff 확인을 배포 필수 항목으로 추가했다.
- 2026-07-27: 서버에는 현재 account/L3 신규 migration이 적용되지 않았다는 사용자 확인을 받아 account release migration을 최초 배포 전에 최종화하기로 했다.
- 2026-07-27: tracked emails `0001` 수정은 서버 미적용 조건과 분리하고 `pg_trgm`을 DB bootstrap 선행 조건으로 되돌리기로 했다.
- 2026-07-27: 추가 리뷰의 감사 사유, 앱 관리자 출처, 필터 확장성, HTTP method, API 중복, resolver 중복 문제를 후속 실행 단계에 추가했다.
- 2026-07-27: 동적 capability 대신 Portal/앱 공통 `user/admin` 고정 역할을 사용하기로 결정했다.
- 2026-07-27: Portal admin은 전역 접근 관리, 앱 admin은 해당 앱 관리만 담당하도록 권한 경계를 확정했다.
- 2026-07-27: 자동 권한 경로의 중복 role 컬럼을 제거하고 역할의 유일한 원본을 `UserAccess.role`로 통합했다.
- 2026-07-27: migration 왕복, backend 246 tests, frontend lint/build, backend/frontend boundary audit를 통과했다. UI audit은 기존 L3 Spider 후보만 보고했다.
- 2026-07-27: Appstore 목록·상세 직렬화의 반복 관리자 판정을 요청 단위 계산으로 전환하기로 했다.
- 2026-07-27: Appstore 18 tests, Django system check, migration check, backend boundary audit, diff check를 통과했다.
- 2026-07-27: 리뷰에서 Portal 일괄 앱 승인 UI의 API 연결 누락, legacy 역할 자동 승격, 사용하지 않는 L3 permission, 매트릭스의 단일 클릭 관리자 승격을 확인했다.
- 2026-07-27: 기존 관리자와 L3 legacy permission 보유자가 없다는 사용자 확인에 따라 데이터 승계 없이 기존 역할은 `user`로 통일하고 legacy permission은 새 migration으로 제거하기로 했다.
- 2026-07-27: 통합 사용자 결정 API에 `approveAllApps`를 연결하고 기존 차단을 유지한 채 미설정·대기 앱만 `user`로 허용하는 회귀 테스트를 추가했다.
- 2026-07-27: `0005` data migration은 기존 역할을 모두 `user`로 정규화하고, L3 `0008` migration은 사용하지 않는 `view_developer_options` permission을 제거하도록 확정했다.
- 2026-07-27: 권한 매트릭스는 단일 클릭 순환 대신 `일반 사용자`/`관리자`/`차단` 명시 선택 메뉴로 변경했다.
- 2026-07-27: backend 250 tests, Django check, migration drift check, frontend lint/build, backend/frontend boundary audit, diff check를 통과했다. UI audit은 이번 변경과 무관한 기존 L3 chart 후보만 보고했다.
- 2026-07-27: 별도 신규 테스트 DB의 전체 migration 재생성은 기존 `gin_trgm_ops` extension 초기화 누락으로 중단되었으며 생성된 임시 DB는 즉시 제거했다. 저장된 테스트 DB에는 account `0005`와 L3 `0008`이 적용된 상태로 회귀 테스트를 통과했다.
- 2026-07-27: 후속 리뷰의 6개 개선점을 모두 적용하되 공개 API 호환성과 기존 데이터 보존을 우선하기로 했다.
- 2026-07-27: `feature` scope는 삭제하지 않고 모든 비-Portal scope에 Portal 선행 조건을 적용해 확장 가능한 보안 기본값으로 완성하기로 했다.
- 2026-07-27: 매트릭스 선택값을 `explicitStatus` 기준으로 바꾸고 미설정·대기·명시 차단을 분리했으며 `자동 규칙 적용`으로 명시 row를 제거할 수 있게 했다.
- 2026-07-27: 기존 요청 ID 승인 API를 canonical 사용자 권한 변경 함수의 adapter로 전환해 상태 전이·감사·일괄 승인 규칙의 원본을 하나로 통합했다.
- 2026-07-27: canonical Portal key 이외 모든 scope에 Portal 선행 조건을 적용하고 auth 응답에 `scope_access`를 추가하되 기존 `app_access`를 유지했다.
- 2026-07-27: 공통 접근 미들웨어와 앱 관리자 검사가 요청 단위 resolver를 공유해 Portal·앱·역할 판정을 scope/정책/UserAccess 3개 일괄 쿼리로 처리하도록 했다.
- 2026-07-27: 새 테스트 DB 생성 직후 `pg_trgm`을 준비하는 test runner와 실제 `MigrationExecutor` 역사 테스트를 추가했다. `0004 → 0005 → 0006` 데이터 보존과 반복 `--keepdb` 초기 데이터 복원을 검증했다.
- 2026-07-27: account 150 tests, auth/appstore/L3/activity/VOC 130 tests, fresh DB migration test, Django check/migration drift, frontend lint/build, backend/frontend boundary audit, diff check를 통과했다. UI audit은 기존 L3 chart 후보만 보고했다.
- 2026-07-27: 후속 리뷰에서 차단 행의 과거 `admin` 역할 재사용 가능성과 AppStore 권한 조회 fallback의 재발 위험을 확인하고 코드·DB 양쪽에서 차단하기로 했다.
- 2026-07-27: `0007` migration에 비허용 `admin` 정규화와 조건부 DB check를 추가하고, canonical service의 회수·역할 없는 재부여를 항상 `user`로 고정했다.
- 2026-07-27: AppStore serializer와 소유권 helper의 관리자 인자를 필수화해 DB 조회를 요청 경계에만 남겼다.
- 2026-07-27: 핵심 6 tests, account/auth/appstore/L3 257 tests, activity/VOC 26 tests, Django check/migration drift/integrity command, backend boundary audit, diff check를 통과했다.
- 2026-07-27: 공개 호환 계층을 더 이상 유지하지 않고 `scope_access`와 canonical 접근 API만 남기라는 사용자 요청을 확정했다.
- 2026-07-27: auth 응답, 접근 신청·결정, 접근 차단 오류를 scope 기반 단일 계약으로 전환하고 Portal 전용 API와 legacy 필드·입력 별칭을 제거했다.
- 2026-07-27: Django 내부 테스트 DB 생성 함수를 감싸던 임시 test runner를 제거하고 `emails` 최초 migration이 `pg_trgm` 확장을 직접 선언하도록 수정했다.
- 2026-07-27: 과거 권한 관리자 감사 action·snapshot을 migration에서 canonical Portal 역할 기록으로 변환하고 UI의 legacy 표시 분기를 제거했다.
- 2026-07-27: 새 테스트 DB migration, backend 679 tests, frontend lint/build, migration drift/integrity, offsite Compose, backend/frontend boundary와 diff 검증을 통과했다. UI·문서 inventory 감사는 이번 변경과 무관한 기존 L3 스타일 및 관리 명령 문서 누락만 보고했다.
- 2026-07-27: account `0005`~`0007`을 서버 최초 적용용 `0005_fixed_access_roles`로 합치고, 초기 권한 감사 marker와 기존 접근 상태·일반 업무 데이터를 보존하는 역사 migration 테스트를 추가했다.
- 2026-07-27: VOC, Emails, Access Stats, Line Dashboard 관리 기능까지 앱 scope admin으로 통일하고 프론트 관리자 메뉴·버튼도 같은 `scope_access` 계약으로 연결했다.
- 2026-07-27: backend 전체 832 tests, frontend lint/build, migration drift/integrity, backend/frontend boundary와 문서 inventory 감사를 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw style 후보만 남았다.
- 2026-07-27: 로컬 개발 DB는 `/tmp/tailwind_dashboard_before_rbac_20260727.dump`에 백업한 뒤 최종 schema·migration ledger로 정합화했다. 운영 서버에는 이 release migration을 아직 적용하지 않았다.
- 2026-07-27: 최종 코드 리뷰에서 감사 migration의 DDL 잠금 확대, Django Admin의 이중 감사 계약, 초기 권한 덮어쓰기 결정자 잔존, 공백 부서 필터 불일치, 감사 `action=all` 오류와 이전 권한 용어를 확인해 최초 운영 적용 전에 모두 보완하기로 했다.
- 2026-07-27: 감사 로그 정규화를 schema 변경 전에 변경 행만 1,000개 단위로 갱신하도록 바꾸고 `0004 → 0005` 역사 migration 테스트로 데이터 보존을 재검증했다.
- 2026-07-27: `UserAccess`와 `AccessPolicyRule`의 Django Admin 쓰기를 제거해 Portal API를 유일한 변경 경로로 만들고, `AccessScope` Admin 감사만 canonical writer를 사용하도록 통일했다.
- 2026-07-27: 초기 권한 덮어쓰기의 결정자 제거, 공백 계정 부서의 현재 소속 fallback, 감사 `action=all` 처리와 앱 관리자 용어를 회귀 테스트와 문서에 반영했다.
- 2026-07-27: 관련 620 tests와 전체 backend 832 tests, migration drift/SQL/integrity/system check, frontend lint/build, backend/frontend boundary, 문서 inventory, diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw style 후보만 보고했다.
- 2026-07-27: 추가 구조 리뷰에서 scope 식별자 변경·삭제, canonical Portal 중복, feature 관리 UI 누락, 감사 참조 유실, 초기 권한 전체 조합 적재 위험을 확인했다.
- 2026-07-27: superuser 운영 방식은 사용자 요청에 따라 범위에서 제외하고, 나머지 scope 수명주기와 확장성 보강을 후속 `account 0006` migration으로 적용하기로 했다.
- 2026-07-27: `account 0006`에 scope key 형식·canonical Portal 제약과 감사 참조 `PROTECT` 상태를 추가하고, Admin 쓰기를 비활성화 중심 수명주기로 제한했다.
- 2026-07-27: 통합 매트릭스와 대기 요청 화면이 활성 app·feature를 같은 API로 관리하도록 변경하고, scope 표시 이름도 API 원본을 사용해 신규 feature 추가 시 프론트 하드코딩을 없앴다.
- 2026-07-27: 초기 권한 부여를 사용자 batch 단위로 바꾸고 feature 제외·완료 marker 단일 기록 회귀 테스트를 추가했다.
- 2026-07-27: account 160 tests와 backend 전체 835 tests, frontend lint/build, Django system/migration/integrity 검사, backend/frontend boundary와 문서 inventory, diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw style 후보만 보고했다.
- 2026-07-27: 런타임 접근 판정과 DB 상태·출처 필터를 Portal·app·비활성 feature의 전체 대표 결과로 비교하는 계약 테스트를 추가했다.
- 2026-07-27: 초기 권한 완료 상태를 `AccessOperationState`로 분리하고 기존 감사 marker 승계·제거 migration, Emails Knox ID 필수 계약, Access Stats 관리자 설명을 정리했다.
- 2026-07-27: account/emails/activity 236 tests와 backend 전체 838 tests, migration 적용·drift·무결성·system check, frontend lint/build, backend/frontend boundary, 문서 inventory, diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw style 후보만 보고했다.
- 2026-07-28: 최종 리뷰 항목 중 배포 무결성 검사 phase 불일치와 superuser 대상 무효 mutation을 수정하기로 했다. 기존 관리자 승계는 사용자 확인에 따라 범위에서 제외했다.
- 2026-07-28: 무결성 명령에 필수 pre/post phase를 추가하고 운영 row-count 절차를 schema 시점에 맞췄다. superuser 대상 6개 mutation을 잠금 직후 `409`로 차단했으며 account 163 tests, Django check/migration drift, frontend lint/build, backend/frontend boundary, 문서 inventory와 diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw style 후보만 보고했다.
- 2026-07-28: 운영 배포에 필요한 최소 보완으로 API 시작 시 자동 migration 제거와 초기 권한 부여의 superuser 제외를 확정했다. dev/OIDC의 명시적 migration 시작 절차는 유지한다.
- 2026-07-28: 초기 권한 명령 7 tests와 account 163 tests, Django system/migration drift, Compose 3종, backend boundary, 문서 inventory, entrypoint 문법과 diff 검증을 통과했다. 로컬 개발 DB post-migration 검사는 과거 `viewer` 역할 2건을 정상적으로 차단했으며 운영 DB 검사는 배포 절차에서 별도로 수행해야 한다.
- 2026-07-28: 최종 정리에서는 저장소 내부 미사용 권한 응답 필드, migration 이후의 런타임 legacy 감사 분기, 프론트 권한 판정 중복만 제거하고 외부 소비 여부가 불명확한 기존 입력 alias는 유지하기로 했다.
- 2026-07-28: Activity·auth·권한 관리 응답과 프론트 전달값을 canonical 필드로 축소하고, 감사 읽기 fallback을 제거했으며 전체 scope payload 계산을 `_ScopeRoleResolver` 하나로 통합했다. Activity 테스트의 UTC/KST 날짜 불일치도 KST 기준으로 고정했다.
- 2026-07-28: 관련 backend 215 tests, Django system/migration drift, frontend lint/build, backend/frontend boundary, 문서 inventory와 diff 검증을 통과했다. production build에는 기존 대형 chunk 경고만 남았다.
- 2026-07-28: 추가 dead-code 감사에서 운영 역할을 소속 역할로 대신 표시하던 fallback, Emails sender ID 정규화 3중 구현, 내부 helper의 불필요한 facade export, Python 미사용 import를 확인해 제거했다.
- 2026-07-28: 추가 정리 후 관련 backend 555 tests, Django system/migration drift, frontend lint/build, backend/frontend boundary, 문서 inventory와 diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw color·inline style 후보만 보고했다.
- 2026-07-28: 최종 dead-code 감사에서 호출이 사라진 접근 selector와 런타임 소비처가 없는 `UserProfile` 체인을 확인했다. 미적용 account `0005`에 프로필 테이블 제거를 통합하기로 했다.
- 2026-07-28: `UserProfile` 모델·자동 생성 signal·service·selector·Admin과 미사용 RBAC selector를 제거했다. `0004 → 0005` 역사 migration을 포함한 account 161 tests, auth/appstore/activity/emails/drone/L3/VOC 464 tests, Django system/migration drift, backend boundary와 문서 inventory 검증을 통과했다.
- 2026-07-28: 미적용 account `0005`~`0007`을 단일 `0005_fixed_access_roles`로 합쳐 역할 정규화부터 scope 불변식·감사 FK 보호·초기 권한 운영 상태 승계까지 한 번에 적용되도록 최종화했다.
- 2026-07-28: 최종 리뷰에서 비활성 scope의 superuser 백엔드 우회와 auth payload 노출 범위가 불일치함을 확인했다. 일반 사용자의 활성 scope 전용 계약은 유지하고 superuser에게만 비활성 scope를 노출하도록 보정한다.
- 2026-07-28: superuser auth payload 보정 후 신규 회귀 테스트, account 162 tests, auth 31 tests, Django system/migration drift, backend boundary, 문서 inventory와 diff 검증을 통과했다. 외부 auth endpoint·env·dummy 계약 변경은 없었다.
- 2026-07-28: 접근 신청 HTTP client와 route별 필수 scope 계산을 각각 하나로 통합하고, query sentinel 정규화·DB 조회 뒤 재필터·빈 Portal payload fallback·권한 화면 scope 이중 source를 제거했다. 단일 대상 test patch loop와 단일 용도 UI 추상화도 실제 호출 계약에 맞게 축소했다.
- 2026-07-28: 호환성 정리 후 account 162 tests와 backend 전체 838 tests, Django system/migration drift, frontend lint/build, backend/frontend boundary, 문서 inventory와 diff 검증을 통과했다. UI audit은 변경 범위 밖의 기존 L3 Spider raw color·측정용 inline style 후보만 보고했다.
- 2026-07-28: 사용자 운영 결정에 따라 초기 권한 일괄 부여를 사용하지 않고 지정한 Django superuser가 최초 관리자를 직접 부여하기로 확정했다. `grant_initial_access`, `AccessOperationState`, marker 승계 migration, 전용 테스트와 운영 문서를 제거했다.
- 2026-07-28: 정리 후 fresh DB 전체 migration, account 155 tests, Django system/migration drift/post-migration 무결성, backend boundary, 문서 inventory와 diff 검증을 통과했다.
- 2026-07-28: 추가 dead-code 검토에서 초기 권한 전용 감사 action, 소비자가 없는 소속 권한 API와 frontend hook, 감사 조회 재정규화, middleware 권한 판정 중복, 참조 0 selector를 확인해 제거하기로 했다.
- 2026-07-28: 미사용 소속 권한 API·frontend hook·fixture·facade, 초기 권한 전용 감사 action, 조회 재정규화, middleware 권한 판정 중복과 참조 0 selector를 제거했다. fresh DB 전체 migration, account 155 tests와 backend 전체 831 tests, Django system/migration drift/post-migration 무결성, frontend lint/build, backend/frontend boundary, 문서 inventory, 잔존 참조와 diff 검증을 통과했다.
