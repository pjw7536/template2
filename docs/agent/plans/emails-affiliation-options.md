# ExecPlan: 메일함 소속 옵션 기준 정리

## 목표
- 메일함 전환 목록이 `station_master` 매칭 여부와 무관하게 활성 `account_affiliation`과 사용자의 Emails 접근 권한만으로 구성되게 한다.

## 현재 상태
- `apps/api/api/account/selectors.py`의 `list_line_sdwt_pairs()`가 활성 소속을 조회한 뒤 `station_master.sdwt_prod_lookup`과 매칭되는 행만 반환한다.
- `apps/web/src/features/emails/components/EmailsShell.jsx`는 위 옵션과 `/api/v1/emails/mailboxes/`의 접근 가능 메일함을 교집합 처리한다.

## 범위
- Account의 line/SDWT 옵션 selector에서 `station_master` 필터를 제거한다.
- 활성 소속 필터와 기존 정렬, API 응답 형태는 유지한다.
- Emails 접근 범위 계산과 메일 조회 권한은 변경하지 않는다.

## 설계
- `/api/v1/account/line-sdwt-options`는 활성 `account_affiliation`의 유효한 `line`/`user_sdwt_prod` 쌍을 반환한다.
- 메일함 화면은 기존대로 이 목록과 Emails 접근 가능 메일함 ID를 교집합 처리한다.
- DB migration, auth/env, 외부 mail sandbox 계약 변경은 없다.

## 실행 단계
- [x] `list_line_sdwt_pairs()`의 `station_master` 조회와 필터를 제거한다.
- [x] 활성 행 포함, 비활성·빈 값 제외, 정렬을 검증하도록 selector 테스트를 갱신한다.
- [x] Account 테스트와 backend boundary audit를 실행한다.

## 검증
- `docker compose -f docker-compose.dev.yml run --rm --no-deps --entrypoint python api manage.py test api.account.tests.AffiliationSelectorTests`
- `npm run agent:audit:api-boundary`
- 기대 결과: 활성 소속은 `station_master` 데이터 없이 모두 반환되고 기존 경계 감사에 신규 위반이 없다.

## 위험과 대응
- 위험: Account line/SDWT 옵션을 사용하는 다른 화면의 선택지가 늘어날 수 있다.
- 대응: 현재 프론트 사용처가 Emails뿐임을 확인했으며, 응답 필드와 정렬은 유지한다.

## 진행 기록
- 2026-08-14: 기존 접근 권한 교집합을 유지하고 `station_master` 필터만 제거하기로 결정했다.
- 2026-08-14: selector의 cross-domain import와 매칭 필터를 제거하고 회귀 테스트를 갱신했다.
- 2026-08-14: Account selector 테스트 4건과 backend boundary audit가 통과했다.
