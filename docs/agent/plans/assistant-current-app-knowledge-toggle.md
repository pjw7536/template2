# ExecPlan: Assistant 현재 앱 지식 토글 복원

## 목표
- ChatWidget의 자동·교차 앱 지식 라우팅 UI를 현재 앱 지식 사용 ON/OFF 토글로 단순화한다.
- ON은 현재 앱의 지원되는 지식만 사용하고, OFF는 앱 배경지식·업무 도구·앱별 과거 메모리 없이 일반 답변을 생성한다.
- 자동 라우팅과 과거 Profile version 재실행 호환 코드를 남기지 않는다.

## 현재 상태
- ChatWidget은 앱별 boolean 토글 하나만 관리한다.
- OFF는 `portal-default`, 빈 Tool 입력, `shared` memory만 사용한다.
- ON은 현재 앱 Profile과 Tool을 바로 실행한다.

## 범위
- 수정: Assistant ChatWidget 토글 상태, surface 선택, 패널 표시, 관련 frontend 테스트.
- 수정: 일반 Profile의 memory partition과 관련 backend 테스트.
- 삭제: 폐기된 자동·교차 앱 실행 경로, 지식 의도 판별기, 답변 경로 metadata, offsite dummy 분기와 과거 계획 문서.
- 제외: DB schema, migration, 외부 RAG/OpenWebUI endpoint, env/Compose.

## 설계
- 프론트 상태는 앱별 boolean `usesAppContext`로 관리하고 앱 이동 시 ON으로 초기화한다.
- 현재 앱의 동적 지식을 지원하면 기존 앱별 Profile을 사용하고, 그 외 앱은 검증된 현재 앱 context만 OpenWebUI에 전달한다.
- OFF는 `portal-default`와 일반 Assistant context를 사용하고 Tool 입력을 비운다.
- `portal-default` v2의 `read_partitions`를 `shared`로 제한해 앱별 조회 결과가 일반 답변 문맥에 들어가지 않게 한다.
- 현재 앱 Profile은 질문을 재분류하지 않고 해당 Tool을 항상 실행한다.
- Profile은 현재 version 하나만 유지하고 폐기된 Profile 요청은 허용하지 않는다.
- API endpoint와 외부 요청 shape는 유지하며 migration/env 변경은 없다.

## 실행 단계
- [x] frontend 모드 상태와 selector를 단순 토글로 복원한다.
- [x] surface를 OFF 일반 답변 / ON 현재 앱 지식으로 제한한다.
- [x] 일반 Profile memory 경계를 수정하고 회귀 테스트를 갱신한다.
- [x] 지식 경로 badge를 제거한다.
- [x] 관련 frontend/backend 테스트와 agent audit를 실행한다.
- [x] 폐기된 Profile·라우터·과거 version 호환 분기를 제거한다.
- [x] 답변 경로 metadata와 offsite dummy 호환 응답을 제거한다.
- [x] 과거 자동 라우팅 문서와 테스트 잔재를 제거하고 전체 검증한다.

## 검증
- 관련 Assistant Vitest를 실행한다.
- Docker Compose `api` 컨테이너에서 `api.assistant` 테스트와 migration check를 실행한다.
- UI, frontend boundary, backend boundary audit를 실행한다.
- 기대 결과: OFF 요청은 `portal-default`, 빈 Tool, `shared` memory만 사용하고 ON 요청은 현재 앱 Profile만 사용한다.
- 결과: Assistant Vitest 96개와 Django `api.assistant` 테스트 58개가 통과했다.
- 결과: 변경 frontend ESLint, production build, UI/frontend/backend boundary audit가 통과했다.
- 결과: `makemigrations --check --dry-run`은 `No changes detected`였다.

## 위험과 대응
- 위험: 폐기된 실행 방식으로 저장된 Run은 재생성할 수 없다.
- 대응: 사용자 요청대로 호환 경로를 제거하고 기존 저장 메시지 조회만 보존한다.
- 위험: 현재 화면 scope가 준비되지 않은 앱에서 ON 요청이 잘못된 Tool 입력을 보낼 수 있다.
- 대응: 기존 readiness 검증과 비활성 사유 표시를 유지한다.

## 진행 기록
- 2026-08-15: 자동 라우팅 도입 전 토글 구현과 현재 v2 memory 경계를 확인하고 복원 범위를 확정했다.
- 2026-08-15: 단일 현재 앱 지식 switch, OFF 일반 surface, 일반 Profile memory 격리와 badge 정리를 구현했다.
- 2026-08-15: frontend/backend 회귀 테스트, migration check, lint, build와 agent audit를 완료했다.
- 2026-08-15: 폐기된 실행 코드·테스트·문서·hotspot 예외를 제거하고 전체 검증을 완료했다.
