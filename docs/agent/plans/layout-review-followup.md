# ExecPlan: 폴더 구조 점검 후속 개선

## 목표
- 로컬 env 합성의 소유권을 local로 옮기고 구조 회귀 검사를 CI에 연결한다.

## 현재 상태
- 공통 apply-env.sh가 로컬 합성 스크립트를 호출한다.
- make tooling-test가 CI에 연결되지 않았다.

## 범위
- env 적용 진입점, CI, 관련 회귀 테스트와 안내.
- API·DB·인증값과 실제 클러스터는 변경하지 않는다.

## 설계
- Makefile의 local 환경은 로컬 wrapper로 전달하고 wrapper가 합성 파일을 공통 도구에 전달한다.
- 공통 도구의 로컬 API 직접 호출은 합성 파일을 요구한다.
- CI 별도 작업에서 tooling 의존성을 설치하고 테스트한다.

## 실행 단계
- [x] 로컬 wrapper와 공통 진입점 분리
- [x] CI 및 동작 회귀 테스트 추가
- [x] 검증 및 문서 갱신

## 검증
- make tooling-test
- make audit-layout audit-tools-test
- bash -n 및 변경 diff 공백 검사

## 위험과 대응
- 로컬 합성 누락: 명시적 입력 검사와 가짜 kubectl 회귀 테스트로 방지한다.
- 서버 checkout: 기존 local 없는 checkout 테스트로 검증한다.

## 진행 기록
- 2026-09-15: 사용자 승인 범위인 구조 의존 방향과 CI 연결 개선을 시작했다.
- 2026-09-15: make tooling-test 60개 통과, audit-tools-test 17개 통과, audit-layout·bash -n·git diff --check 통과. 실제 클러스터 변경 없이 가짜 kubectl로 병합 우선순위·Namespace·임시 파일 정리를 검증했다. 원격 CI 실행은 아직 수행하지 않았다.
