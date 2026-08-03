# ExecPlan: access-stats 역할별 동기화 제한

## 목표
- `access-stats` 접근 권한이 있는 모든 로그인 사용자가 외부 API 동기화를 요청할 수 있게 한다.
- 일반 사용자의 실제 외부 API 동기화는 전역 기준 6시간에 한 번만 수행한다.
- `access-stats admin`과 슈퍼유저는 6시간 제한을 우회한다.
- 제한으로 동기화를 건너뛰면 서버가 반환한 사유를 사용자에게 알린다.

## 현재 상태
- 프런트 동기화 버튼과 동기화 API는 모든 `access-stats` 사용자에게 열려 있다.
- 일반 사용자는 마지막 실제 시도 후 5분 동안 후속 동기화를 건너뛰고 관리자는 제한을 우회한다.
- 프런트는 skip 결과를 버튼 문구로만 표시하고 서버의 구체적인 사유는 알리지 않는다.
- 동기화 상태의 `updated_at`은 성공과 실패를 포함한 마지막 실제 시도를 나타낸다.

## 범위
- 수정: activity 동기화 service/View/테스트, access-stats 동기화 버튼, 관련 ExecPlan.
- 제외: `access-stats` 앱 접근 승인, 수동 붙여넣기 권한, DB schema, 외부 API/env 계약.

## 설계
- 공통 앱 접근 permission은 유지해 `access-stats` 접근이 허용된 로그인 사용자만 API에 도달하게 한다.
- View는 기존 공통 역할 판정으로 `access-stats admin`과 슈퍼유저의 제한 우회 여부를 결정한다.
- 일반 사용자의 마지막 실제 시도 후 6시간 이내 요청은 `skipped=true`로 반환하고 외부 API를 호출하지 않는다.
- 실패한 실제 시도도 일반 사용자의 6시간 제한에 포함해 외부 서버 장애 중 반복 호출을 막는다.
- 프런트는 skip 응답의 `reason`을 정보 toast 설명으로 표시하고 버튼 상태도 유지한다.
- 기존 `ExternalAppUsageSyncState`를 재사용하므로 migration은 필요하지 않다.

## 실행 단계
- [x] 일반 사용자 6시간 제한과 관리자·슈퍼유저 우회 테스트를 갱신한다.
- [x] View와 service에 역할별 제한 계약을 적용한다.
- [x] 프런트에서 skip 사유 toast를 표시한다.
- [x] backend/web 테스트와 frontend/backend/UI/문서 audit을 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.activity`
- `npm run web:test`
- `npm exec -- eslint src/features/access-stats/pages/AccessStatsPage.jsx` (`apps/web` 기준)
- `npm run agent:audit:api-boundary`
- `npm run agent:audit:web-boundary`
- `npm run agent:audit:ui`
- `npm run agent:audit:docs`

## 위험과 대응
- 위험: 동시에 들어온 요청이 throttle을 우회해 외부 API를 중복 호출할 수 있다.
- 대응: 기존 단일 상태 row와 `select_for_update()` transaction으로 실제 시도 시작 시점을 직렬화한다.
- 위험: 외부 API 장애 중 재시도가 몰릴 수 있다.
- 대응: 성공 시각이 아니라 마지막 실제 시도 시각인 `updated_at`을 일반 사용자의 6시간 기준으로 사용한다.
- 위험: 수동 붙여넣기까지 일반 사용자에게 열릴 수 있다.
- 대응: 버튼별 권한을 분리하고 수동 붙여넣기 View의 `admin` 검사는 유지한다.
- 위험: 프런트가 서버와 다른 제한 사유를 안내할 수 있다.
- 대응: 프런트 고정 문구가 아니라 응답의 `reason`을 표시한다.

## 진행 기록
- 2026-08-03: `access-stats` 사용자 전체 허용, 전역 6시간 제한, 실패 시도 포함으로 계약을 확정했다.
- 2026-08-03: backend activity 테스트 26개와 web 테스트 14개, 대상 ESLint, backend/frontend 경계 감사, 문서 감사를 통과했다.
- 2026-08-03: UI 감사는 이번 변경과 무관한 기존 L3 Spider raw color와 기존 inline style 후보로 실패했으며 범위 밖 코드는 수정하지 않았다.
- 2026-08-03: 후속 요청에 따라 일반 사용자는 전역 5분 제한, `access-stats admin`과 슈퍼유저는 제한 우회, skip 사유는 toast 표시로 계약을 변경했다.
- 2026-08-03: backend activity 테스트 27개와 web 테스트 14개, 대상 ESLint, backend/frontend 경계 감사, 문서 감사를 통과했다.
- 2026-08-03: UI 감사는 기존 L3 Spider raw color와 기존 측정용 inline style 후보만 다시 보고해 요청 범위 밖 코드는 유지했다.
- 2026-08-03: 최종 요청에 따라 일반 사용자의 전역 제한을 6시간으로 조정하고 관리자·슈퍼유저 우회와 skip 사유 toast를 유지했다.
- 2026-08-03: 6시간 계약으로 backend activity 테스트 27개와 backend 경계·문서 감사를 다시 통과했다.
