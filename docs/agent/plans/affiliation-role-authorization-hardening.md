# ExecPlan: 소속 역할 권한 강화

## 목표
- `viewer/member/manager` 역할을 읽기·일반 변경·삭제·권한 관리 capability로 일관되게 판정한다.
- Emails에서 member는 이동할 수 있지만 삭제는 manager만 수행하도록 서버에서 강제한다.
- 소속 변경은 manager만 승인·거절하고 자기 요청 처리와 동시 처리 경합을 차단한다.
- manager가 제품 API와 Account Members 화면에서 소속 접근 역할을 부여·변경·회수할 수 있게 한다.
- 소속 식별자와 역할 값의 DB 무결성을 강화한다.

## 현재 상태
- 소속 역할은 `apps/api/api/account/models.py`의 `UserSdwtProdAccess`가 소유한다.
- 현재 소속은 명시 행이 없어도 member로 취급하며, 과거 소속 viewer 접근은 유지한다.
- `grant_or_revoke_access`에는 현재 소속 회수 및 마지막 manager 회수 방지가 일부 구현되어 있다.
- Emails 조회·이동·삭제는 접근 가능한 소속 집합만 사용하고 역할별 capability를 구분하지 않는다.
- Account Members 화면은 멤버와 승인 요청을 조회하지만 역할 변경·회수 UI는 없다.
- 작업 시작 시 account 권한 화면과 서비스에 사용자 선행 staged 변경이 존재한다.

## 범위
- 수정할 영역:
  - `apps/api/api/account`: capability, 승인 트랜잭션, 관리 API, 모델·migration·무결성 검사·테스트
  - `apps/api/api/emails`: 이동·삭제 capability 검사와 테스트
  - `apps/web/src/features/account`, `apps/web/src/lib/account`: manager 권한 관리 UI와 React Query 연동
  - account/emails 관련 문서
- 수정하지 않을 영역:
  - 과거 소속 viewer 접근 유지 정책
  - TTTM Spider 프록시
  - Observer 및 Line Dashboard 데이터 범위

## 설계
- 데이터 흐름:
  - Account 서비스가 소속별 실효 역할과 capability 판정을 소유한다.
  - 다른 도메인은 `api.account.services` 파사드만 통해 capability를 확인한다.
  - Emails 읽기는 기존 접근 집합을 유지하고, 이동은 source/target 모두 `write`, 삭제는 source에 `delete`를 요구한다.
  - 소속 관리 API는 기존 `grant_or_revoke_access`를 호출하며 manager 또는 기존 특권 사용자만 허용한다.
- public API/facade 영향:
  - account 서비스 파사드에 소속 capability 판정 함수를 추가한다.
  - `/api/v1/account/affiliation/access`에 grant/update 및 revoke 계약을 추가한다.
- migration/env/auth 영향:
  - `Affiliation.user_sdwt_prod`에 공백·대소문자 무시 유일 제약을 적용한다.
  - `Affiliation.user_sdwt_prod`의 빈 값·앞뒤 공백을 DB check constraint로 차단한다.
  - `UserSdwtProdAccess.role`에 CheckConstraint를 추가한다.
  - env 계약 변경은 없다.

## 실행 단계
- [x] 공통 소속 capability 판정과 무결성 제약을 추가한다.
- [x] 소속 승인·거절을 manager 전용, 자기 처리 금지, 행 잠금 기반으로 변경한다.
- [x] manager 권한 관리 API와 Account Members UI를 추가한다.
- [x] Emails 이동·삭제에 역할별 capability를 적용한다.
- [x] 기존 문서와 역할 설명을 새 정책에 맞춘다.
- [x] migration, Django 테스트, frontend build 및 경계/UI 감사를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.account api.emails api.assistant --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.auth --noinput`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check_access_permission_integrity --phase post-migration`
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- frontend package의 기존 build 또는 test 명령

## 위험과 대응
- 위험: 기존 staged account 변경과 충돌할 수 있다.
- 대응: 현재 파일을 기준으로 최소 증분 편집하고 기존 공개 export와 UI 구조를 보존한다.
- 위험: 기존 데이터에 대소문자·공백 중복 소속이나 잘못된 역할이 있으면 migration이 실패한다.
- 대응: 제약 추가 전 데이터 검사 migration과 관리 명령으로 구체적인 문제 행을 보고한다.
- 위험: manager 강등 동시 요청이 마지막 manager 불변조건을 깨뜨릴 수 있다.
- 대응: 대상 소속 행을 잠근 트랜잭션에서 마지막 manager 여부를 재검사한다.

## 진행 기록
- 2026-07-29: member 이동 허용, manager 삭제·승인·권한 관리, 마지막 manager 보호 정책을 확정했다.
- 2026-07-29: 기존 staged 변경을 보존하고 Account Members 화면과 기존 서비스에 증분 적용하기로 했다.
- 2026-07-29: 동시 진행된 앱별 소속 데이터 범위 변경을 보존하고, Emails 작업 권한은 앱 범위와 소속 capability를 모두 만족하도록 통합했다.
- 2026-07-29: `data_scope=all`만으로 운영 특권이 생기지 않게 Emails `admin` 역할과 `all` 범위를 모두 요구하도록 보강했다.
- 2026-07-29: Django account/emails/assistant 270개, auth 31개, Emails 최종 57개 테스트가 통과했다.
- 2026-07-29: backend/frontend boundary, frontend lint/build는 통과했다. UI audit은 범위 밖 L3 raw color와 측정·위치 계산용 inline style 후보를 보고해 비통과로 기록했다.
