# ExecPlan: L3 Spider 개발자 옵션 권한

## 목표
- `l3_spider.view_developer_options` Django permission을 생성한다.
- 권한이 있는 사용자에게만 개발자 옵션 버튼을 노출하고 관련 API 호출을 허용한다.

## 범위
- 수정: L3 Spider model permission과 신규 migration.
- 추가: L3 Spider DRF permission class.
- 수정: Meta capability 응답과 개발자 endpoint 권한.
- 수정: 프론트 조건부 렌더링과 Meta placeholder.
- 수정: 권한별 API 회귀 테스트와 문서.
- 제외: 일반 사용자/그룹에 대한 자동 권한 배정.

## 설계
- custom permission은 `L3SpiderLineNameRule` model Meta에 선언한다.
- superuser는 Django 기본 `has_perm` 동작으로 항상 허용한다.
- Meta view는 서비스의 글로벌 cache dict를 수정하지 않고 응답 복사본에 `canUseDeveloperOptions`를 추가한다.
- 개발자 endpoint는 같은 permission을 서버에서도 검사해 UI 우회를 차단한다.
- 프론트는 Meta capability가 true일 때만 `L3SpiderDeveloperSheet`를 렌더링한다.

## 실행 단계
- [x] custom permission과 migration 추가
- [x] DRF permission 및 Meta capability 구현
- [x] 프론트 조건부 렌더링 구현
- [x] 권한별 테스트와 전체 검증

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.l3_spider --keepdb`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py check`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations --check --dry-run l3_spider`
- `npm run web:build`
- 변경 파일 ESLint, frontend/backend boundary audit, `git diff --check`

## 위험과 대응
- 위험: 프론트만 숨기면 직접 API 호출이 가능하다.
- 대응: DRF permission으로 endpoint도 403 처리한다.
- 위험: 글로벌 Meta cache에 사용자 capability가 섞일 수 있다.
- 대응: view에서 cached result를 복사한 뒤 capability를 추가한다.
- 위험: dev 사용자가 권한이 없어 기능 검증이 막힐 수 있다.
- 대응: 현재 Dummy User는 superuser이므로 자동 허용된다.

## 진행 기록
- 2026-07-14: 현재 개발자 버튼은 무조건 렌더링되고 endpoint는 로그인 사용자 모두 허용함을 확인했다.
- 2026-07-14: custom permission과 migration을 추가하고 개발 DB에 적용했다. `admin`과 `Dummy User`는 superuser라 권한이 허용되며, 일반 사용자에게는 자동 부여하지 않았다.
- 2026-07-14: Meta capability, 개발자 endpoint 서버 권한 검사, 프론트 조건부 렌더링을 구현했다.
- 2026-07-14: L3 Spider API 테스트 52개, Django check, migration drift 검사, 웹 build, ESLint, frontend/backend boundary audit, `git diff --check`를 통과했다. UI audit은 기존 `L3SpiderChart.jsx`의 raw color/inline style만 보고했으며 이번 변경에서 추가된 위반은 없다.
