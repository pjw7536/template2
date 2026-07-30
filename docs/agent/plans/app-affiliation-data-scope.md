# ExecPlan: 앱별 소속 데이터 범위 분리

## 목표
- Portal·앱 접근 역할과 앱별 소속 데이터 범위를 분리한다.
- 소속 보안 경계가 필요한 앱만 현재 소속과 명시 grant를 사용해 데이터를 제한한다.
- 기존 Emails·Assistant의 전역 소속 접근을 앱별 범위로 전환하고 교차 앱 권한 전파를 차단한다.

## 현재 상태
- `AccessScope`와 `UserAccess`가 Portal·앱 접근 및 `user/admin` 역할을 관리한다.
- `UserSdwtProdAccess`는 앱 문맥 없이 소속 데이터 접근과 소속 운영 역할을 함께 저장한다.
- Emails와 Assistant가 공통 `get_accessible_user_sdwt_prods_for_user` 결과를 사용한다.
- Account·Emails·Web 권한 관리 영역에 선행 미커밋 변경이 있으므로 현재 파일 상태를 기준으로 증분 편집해야 한다.
- 소속 역할·앱별 데이터 범위·권한 감사 스키마는 미적용 통합 migration
  `0006_account_authorization_system.py`에 포함한다.

## 범위
- 수정할 영역:
  - `api.account` 모델, migration, selector, service facade, 관리 API, 테스트
  - Emails·Assistant의 소속 데이터 범위 resolver 호출
  - Account 권한 관리 화면의 앱별 소속 범위 편집
  - Account API·모듈 문서와 운영 무결성 검사
- 수정하지 않을 영역:
  - 기존 Portal 선행 조건과 `user/admin` 역할 계약
  - Observer·Line Dashboard·L3 Spider의 도메인별 객체 권한
  - 외부 인증·env·Compose 계약
  - 선행 미커밋 변경의 기능 및 UI 구조

## 설계
- `AccessScope`는 `data_scope_type=none|affiliation`과 `include_current_affiliation`을 선언한다.
- `UserAccess`는 앱 역할과 독립적으로 `data_scope_mode=default|all`을 저장한다.
- `UserScopeAffiliationGrant`는 `(user, scope, affiliation)`별 활성·만료 가능한 명시 데이터 grant를 저장한다.
- `api.account.services`가 앱 접근을 포함한 실효 소속 범위 resolver와 관리 쓰기를 제공한다.
- `none` scope는 소속 판정을 적용하지 않고, `affiliation` scope만 현재 소속·명시 grant·all을 계산한다.
- 기존 `UserSdwtProdAccess`는 이번 단계에서 소속 운영 capability 계약을 보존한다.
- migration은 Emails·Assistant를 `affiliation/current`로 설정하고 기존 전역 소속 행을 두 앱의 명시 grant로 복제한다.
- 기존 Emails admin은 현재 전체 메일함 동작을 보존하도록 `data_scope_mode=all`로 전환한다.
- 신규 앱 admin은 자동으로 전체 소속 범위를 받지 않는다.

## 실행 단계
- [x] 모델·제약·데이터 migration을 추가한다.
- [x] 소속 범위 selector/resolver와 관리 service/API를 추가한다.
- [x] Emails·Assistant를 scope-aware resolver로 전환한다.
- [x] 권한 매트릭스에서 소속 기반 앱의 데이터 범위를 편집할 수 있게 한다.
- [x] 서비스·selector·API·교차 앱 격리 테스트를 추가한다.
- [x] 문서와 무결성 검사 명령을 갱신한다.
- [x] Docker migration/test와 backend/frontend/UI audit을 실행한다.
- [x] 반복 grant가 기존 `all` 범위를 보존하고 범위 변경 감사를 누락하지 않게 한다.
- [x] 만료·비활성 비수동 grant를 명시적인 수동 grant로 전환할 수 있게 한다.
- [x] 레거시 grant backfill을 고정 크기 청크로 처리한다.
- [x] 활성 소속 검증과 grant 쓰기를 같은 transaction 잠금 범위에 둔다.
- [x] 보완 회귀 테스트와 경계 검증을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.emails api.assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- frontend package의 기존 lint/build 명령
- `git diff --check`

## 위험과 대응
- 위험: 기존 전역 소속 grant를 모든 앱에 복제하면 권한이 확대될 수 있다.
- 대응: 기존에 전역 resolver를 소비하던 Emails·Assistant에만 변환한다.
- 위험: Emails admin의 기존 전체 메일함 접근이 사라질 수 있다.
- 대응: migration에서 기존 허용된 Emails admin만 명시적 `all`로 전환한다.
- 위험: 현재 소속 변경 시 stale grant가 남을 수 있다.
- 대응: 현재 소속은 파생 범위로 계산하고 명시 grant와 분리한다.
- 위험: UI/API가 `none` scope에 데이터 grant를 생성할 수 있다.
- 대응: serializer, service, DB 제약 가능한 범위, 무결성 검사에서 중복 차단한다.
- 위험: 선행 미커밋 변경과 충돌할 수 있다.
- 대응: 현재 상태를 기준으로 작은 patch를 적용하고 선행 공개 계약을 보존한다.
- 위험: 반복 앱 grant가 명시적 `all`을 `default`로 되돌릴 수 있다.
- 대응: `allowed`에서 `allowed`로 유지되는 결정은 기존 데이터 범위를 보존한다.
- 위험: 만료된 `policy/external` 행의 고유 제약 때문에 같은 소속을 수동으로 다시 부여하지 못할 수 있다.
- 대응: 활성·미만료 자동 grant만 보호하고, 효력이 끝난 행은 감사 전후 값을 남기며 `manual`로 전환한다.
- 위험: 활성 소속 검증 직후 다른 transaction이 소속을 비활성화할 수 있다.
- 대응: 선택 소속을 쓰기 transaction 안에서 `select_for_update`로 다시 검증한다.
- 위험: 레거시 grant가 많으면 migration process가 전체 데이터를 메모리에 보관할 수 있다.
- 대응: 입력 iterator와 출력 `bulk_create`를 같은 고정 청크 크기로 제한한다.

## 진행 기록
- 2026-07-29: 앱 접근 RBAC와 앱별 소속 데이터 범위를 분리하는 구현을 시작했다.
- 2026-07-29: 기존 전역 범위 소비 앱은 Emails·Assistant로 확인했고, 나머지 앱은 `none`으로 유지하기로 했다.
- 2026-07-29: 앱별 grant, 명시적 `all`, 중앙 fail-closed resolver, 관리 API/UI와 감사 로그를 구현했다.
- 2026-07-29: 기존 전역 grant는 Emails·Assistant로 복제하고 기존 Emails admin만 `all`로 보존하는 migration을 추가했다.
- 2026-07-29: Account 전체 199개, 핵심 데이터 범위 9개, Emails 56개, Assistant 19개, frontend build/lint, 경계·문서 audit, 운영 무결성 검사를 통과했다.
- 2026-07-29: 전체 UI audit은 이번 변경과 무관한 기존 L3 Spider raw color/inline style 및 선행 Account inline style 후보 때문에 비정상 종료했으며, 이번 신규 UI 파일에는 해당 후보가 없다.
- 2026-07-30: 코드리뷰에서 확인한 반복 grant, 만료 자동 grant, migration 메모리, 소속 활성화 경쟁 조건 보완을 시작했다.
- 2026-07-30: 반복 grant의 `all` 보존과 회수 시 별도 범위 감사, 만료 자동 grant의 수동 전환, 잠금 기반 활성 소속 검증, 1,000개 단위 backfill을 구현했다.
- 2026-07-30: 핵심 회귀 12개, Account 202개, Emails·Assistant 76개 테스트와 migration check, 운영 무결성, Django system check, backend boundary audit을 통과했다.
