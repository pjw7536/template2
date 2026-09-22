# ExecPlan: 루트 실행·의존성 파일 정리

## 목표
- 루트 npm workspace·node_modules·Compose 연결 파일을 제거하고 Makefile을 진입점으로 사용한다.

## 현재 상태
- Web 독립 package.json·lockfile이 이미 존재한다. 도구 Node 테스트는 js-yaml을 루트에서 간접 사용한다.
- 실제 Compose는 local·deploy에 있고 루트 파일은 include만 담당한다.

## 범위
- package 관리·Makefile·CI·도구 검사·현재 문서와 스킬 참조.
- 업무 코드·DB·환경 설정·실제 배포는 유지한다. 기존 사용자 변경은 보존한다.

## 설계
- Web 의존성은 apps/portal/web, 도구 의존성은 apps/tooling에서 개별 설치한다.
- 도구 js-yaml은 기존 설치 버전을 고정한다. Web lockfile은 기존 버전을 유지한다.
- make install, web-dev/test/lint/build/preview, audit, tooling-test를 제공한다.
- 루트 package.json·lockfile·Compose 파일을 삭제하고 node_modules는 각 프로젝트에서 재설치한다.
- CI cache 입력과 실행 명령을 개별 lockfile·Makefile로 전환한다.

## 실행 단계
- [x] package·Makefile·CI 분리 및 루트 파일 제거
- [x] 루트 구조 검사·현재 문서·스킬 갱신
- [x] 독립 설치·Web·도구·Compose·서버 검사

## 검증
- make install 후 루트 node_modules 없이 make web-test web-lint web-build.
- make audit, make tooling-test, make compose-check.
- Helm이 포함된 PATH에서 make server-check APP=all.
- 문서 링크·이전 명령 잔존 검사·git diff --check.

## 위험과 대응
- 도구의 암묵적 Node 의존성을 명시하고 실제 루트 node_modules 제거 후 검증한다.
- 과거 ExecPlan은 당시 기록을 보존한다. 현재 규칙·스킬·문서는 새 명령을 사용한다.

## 진행 기록
- 2026-09-15: 사용자 요청에 따라 루트 호환 파일까지 제거하는 작업 시작.

- 2026-09-15: 루트 package·lockfile·node_modules와 Compose 연결 파일 4개를 제거했다. Web 기존 독립 lockfile을 사용하고 도구에는 기존 js-yaml 4.3.0을 직접 선언했다.
- 2026-09-15: make install로 두 프로젝트를 독립 설치했다. CI cache-dependency-path와 실행 명령을 개별 lockfile·Makefile로 전환했다.
- 2026-09-15: make web-test web-lint web-build 통과(54개 파일, 206개 테스트). 기존 큰 chunk 안내는 유지했다.
- 2026-09-15: PATH="$PWD/.tools/bin:$PATH" make audit tooling-test compose-check server-check APP=all 통과. 감사 단위 테스트 17개, 배포·구조 회귀 58개, 전체 서버 원본 검사 통과.
- 2026-09-15: 현재 문서 링크와 git diff --check 통과. 루트 node_modules 없이 js-yaml이 apps/tooling에서 resolve되는 것을 검사했다.
- 2026-09-15: 업무 코드·DB·실제 배포는 변경하지 않았고 commit·push하지 않았다.
