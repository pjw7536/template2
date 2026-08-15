# ExecPlan: APITable Portal SSO Work Hub

> 상태: 2026-08-05 `grist-work-hub-replacement.md`에 의해 대체된 과거 실행 기록입니다.

## 목표
- Grist 기반 Work Hub를 APITable OSS 기반으로 교체한다.
- Portal에 로그인한 사용자가 별도 로그인 화면 없이 APITable 업무일지로 이동하게 한다.
- 설비 기준정보 필드는 일반 사용자에게 읽기 전용으로 강제하고, WorkLog에는 사용자 로그와 사진 첨부 필드를 제공한다.
- 기존 Grist volume과 기능 플래그를 보존해 검증 실패 시 원복할 수 있게 한다.

## 현재 상태
- `/work-hub`와 `api.work_hub`는 APITable Space/datasheet 계약과 Portal SSO launch API를 사용한다.
- dev/OIDC/prod Compose는 APITable을 선택적 `work-hub` profile로 실행하며 기존 Grist volume은 원복용으로만 보존한다.
- 로컬 APITable에는 `DEV_ALPHA` Space, Equipment/WorkLog/Task datasheet와 3/3/2 demo record가 멱등 생성되어 있다.
- Portal ticket의 최초 session 교환과 동일 `jti` 재사용 401 거부를 실제 컨테이너에서 확인했다.

## 범위
- 수정: APITable 파생 이미지, Portal→APITable 단기 SSO ticket, Work Hub Django 모델·client·서비스·명령·테스트, launcher, Compose/env/Make/Nginx, 관련 문서.
- 유지: `/work-hub`, `/api/v1/work-hub/context`, `work-hub` AccessScope, account/observer 공개 계약, 기존 Grist volume.
- 제외: Grist record 자동 이관, APITable grid/OT 엔진 수정, APITable branding 제거, 외부 GitHub fork/PR 생성.

## 설계
- APITable은 Portal과 독립 서비스로 실행하고 공식 all-in-one 1.13.0-beta.1 이미지를 digest로 고정한다.
- 파생 이미지에는 APITable의 `AuthServiceFacade` 확장과 SSO/provisioning controller class만 추가한다. upstream application class는 수정하지 않는다.
- Portal은 현재 OIDC session의 `issuer + subject`를 포함한 HS256 ticket을 60초 동안 발급한다. APITable은 issuer/audience/signature/expiry/jti를 검증하고 Redis에서 jti를 한 번만 사용하게 한 뒤 내부 사용자를 JIT 연결하고 APITable session을 발급한다.
- `issuer + subject`의 SHA-256을 APITable user UUID로 사용하고 email/name은 로그인 시 동기화한다.
- 소속 하나당 APITable Space 하나와 Equipment/WorkLog/Task datasheet를 연결한다.
- Equipment의 자동 필드는 APITable field permission으로 root team에 Reader를 부여하며 space owner와 관리자는 계속 수정할 수 있다.
- 데이터레이크/Observer 동기화는 APITable Fusion API token으로 Equipment를 멱등 upsert한다.
- WorkLog의 `사진`은 APITable Attachment field로 제공하고, 작성자·생성/수정 시각 field를 함께 둔다.
- 기존 Grist volume은 삭제하지 않고 Compose에서 이름만 분리해 보존한다.

## 실행 단계
- [x] APITable 파생 이미지와 Portal SSO/provisioning overlay를 추가한다.
- [x] dev/OIDC/prod Compose와 env/Make 계약을 APITable로 교체한다.
- [x] Django Work Hub 모델·migration·client·서비스·명령·Webhook을 APITable 계약으로 교체한다.
- [x] launcher가 사용자별 단기 ticket을 발급받아 APITable로 top-level 이동하게 한다.
- [x] demo Space/datasheet/field permission/record/Portal mapping seed를 구현한다.
- [x] 문서와 운영·원복 절차를 갱신한다.
- [x] backend/frontend/Compose/overlay build와 실제 로컬 SSO·seed를 검증한다.

## 검증
- `docker build -f deploy/apitable-portal-sso/Dockerfile deploy/apitable-portal-sso`
- `docker compose -f docker-compose.dev.yml config`
- `docker compose -f docker-compose.oidc.yml config`
- `docker compose -f docker-compose.yml config`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.work_hub api.observer api.account --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py seed_apitable_demo`
- frontend Work Hub test와 build
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `bash scripts/agent/check_compose_configs.sh`

## 위험과 대응
- 위험: APITable 공개 SSO가 Enterprise 기능이라 upstream Community image에는 구현이 없다.
- 대응: 이미 존재하는 Community 확장 interface를 이용한 별도 파생 이미지를 만들고 수정 class를 최소화한다.
- 위험: Portal ticket이 재사용되면 session 탈취로 이어질 수 있다.
- 대응: 60초 expiry, audience/issuer 검증, Redis `SET NX` 기반 jti 1회 사용, 허용된 상대 redirect만 적용한다.
- 위험: APITable all-in-one은 운영 권장 구성이 아니다.
- 대응: dev에서는 all-in-one을 사용하고 OIDC/prod는 동일 overlay가 포함된 사내 registry의 분리형/승인 이미지를 `APITABLE_IMAGE`로 주입할 수 있게 계약을 분리한다.
- 위험: Grist와 APITable 데이터 형식이 호환되지 않는다.
- 대응: 기존 Grist volume을 보존하고 새 APITable mapping은 별도 migration에서 비활성 상태로 전환·재등록한다.

## 진행 기록
- 2026-08-04: APITable OSS와 Portal 단일 로그인을 필수 조건으로 확정했다.
- 2026-08-04: Portal OIDC session에서 발급하는 1회용 handoff ticket을 APITable Community 확장점에서 검증하는 방식으로 구현 범위를 최소화했다.
- 2026-08-04: upstream all-in-one `init-appdata.sh`의 닫히지 않은 table prefix quote 때문에 Liquibase 초기화가 실패해 동일 script의 오타만 overlay에서 보정했다.
- 2026-08-04: SMTP가 비활성인 환경에서도 멤버 동기화가 가능하도록 mail invitation 대신 APITable 내부 invitation member 생성을 사용했다.
- 2026-08-04: demo seed를 두 번 실행해 같은 Space/datasheet와 3/3/2 record를 재사용하는 것을 확인했다.
- 2026-08-04: Portal ticket 교환은 APITable session cookie를 발급하고 같은 ticket 재사용은 401로 거부하는 것을 확인했다.
- 2026-08-04: `DEV_ALPHA` 소속 Portal 사용자의 session으로 WorkLog node API가 성공해 APITable Space 멤버 연결까지 확인했다.
- 2026-08-04: 원복용 Grist table을 Django state에서 제거하면 테스트 DB flush가 FK를 누락하는 문제를 발견해, 서비스에서 사용하지 않는 호환 모델로 state에 보존했다.
- 2026-08-04: Django Work Hub·Observer·Account 294개, frontend Work Hub 3개, ESLint, production build, backend/frontend/UI boundary, Compose 3종 검증을 통과했다.
