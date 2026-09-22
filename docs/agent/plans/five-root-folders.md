# ExecPlan: 최상위 관리 폴더 다섯 개로 정리

## 목표
- 관리 폴더는 apps, data, deploy, docs, local로 제한한다.
- Compose 본문은 용도별 폴더에 두고 Makefile에서 실행한다. 루트 Compose 파일은 호환 연결만 유지한다.

## 현재 상태
- 앱 소스는 이전 계획에 따라 이동 완료. scripts와 airflow 호환 폴더·루트 문서가 남아 있다.
- 사용자가 삭제한 y5pull·y5push는 복구하지 않는다. 기존 staged/unstaged 변경은 보존한다.

## 범위
- 도구·Compose·문서 경로, Makefile, CI, Agent 규칙·검사.
- 업무 코드·인증·DB·운영 배포는 변경하지 않는다. 데이터는 삭제하지 않는다.

## 설계
- scripts/agent와 scripts/tests는 apps/tooling 아래로 이동한다.
- CI SQL 입력은 deploy/portal/test, 파일 진단 도구는 local/portal/scripts에 둔다.
- 개발 조합은 local/compose/{dev,airflow}.yml, CI 본문은 deploy/portal/compose/test.yml.
- 이전 서버 조합은 deploy/shared/compose/{oidc,prod}.yml. 기존 root Compose는 include wrapper로 남긴다.
- Compose project 이름 tailwind, airflow, tailwind-test와 DB volume 이름을 유지한다.
- 루트 airflow의 잔여 로그·설정은 ignored data/airflow/legacy-root에 보존한다.
- 생성 cache는 .tools로 옮기며 node_modules와 도구 필수 숨김 디렉터리는 예외다.

## 실행 단계
- [x] 도구·문서·잔여 폴더 이동
- [x] Compose 원본·Makefile·CI 참조 전환
- [x] Agent 규칙·root 구조 검사·회귀 테스트 갱신
- [x] 검증과 실행 안내 기록

## 검증
- npm run agent:audit, node --test apps/tooling/tests/*.test.cjs.
- 신·구 Compose config의 서비스·project 이름·volume·build context 비교.
- Makefile dry-run 및 소스·local 없는 server-check.
- 경로 변경만 있는 CI API 이미지 build 및 Docker Compose config 검사.
- git diff --check와 현재 문서 상대 링크 확인.

## 위험과 대응
- Compose 상대 경로는 새 파일 위치를 기준으로 명시적으로 갱신한다.
- 캐시·기존 로그는 실행 경로에서 분리해 보존한다. DB volume은 건드리지 않는다.
- 과거 ExecPlan은 역사 기록으로 유지하며 현재 안내만 갱신한다.

## 진행 기록
- 2026-09-15: 사용자 확정 방향으로 구현 시작.

- 2026-09-15: 도구는 apps/tooling, CI SQL은 deploy/portal/test, 파일 진단 도구는 local/portal/scripts로 이동했다. 삭제된 y5 스크립트는 복구하지 않고 끊어진 Makefile target을 정리했다.
- 2026-09-15: 루트 airflow의 실제 로그·설정은 data/airflow/legacy-root로 그대로 이동하고 루트 Python cache는 .tools/cache에 보존했다. 실제 데이터 삭제·DB 초기화는 하지 않았다.
- 2026-09-15: Compose project·volume·mount·image·build context·port·network·환경 변수 fingerprint를 이동 전후 비교했다. SQL 파일 위치 변경을 제외한 실행 계약이 동일했다.
- 2026-09-15: 명시적 상대 AIRFLOW_PROJ_DIR은 새 standalone 정의 위치 기준이며 절대 경로 사용을 문서화했다. 기본 경로와 절대 override의 기존 동작은 회귀 테스트로 확인했다.
- 2026-09-15: 최종 검증 통과: npm run agent:audit(단위 테스트 17개 포함), PATH="$PWD/.tools/bin:$PATH" node --test apps/tooling/tests/*.test.cjs(58개), make compose-check, make build-ci-api, PATH="$PWD/.tools/bin:$PATH" make server-check APP=all.
- 2026-09-15: 신·구 Compose 연결 동일성, Makefile 실행 경로 dry-run, 문서 상대 링크, git diff --check 모두 통과. 업무 소스를 수정하지 않아 전체 업무 테스트는 반복하지 않았다.
- 2026-09-15: 실제 서버 배포·commit·push는 실행하지 않았다. node_modules와 도구 필수 숨김 디렉터리는 최상위 관리 폴더 제한의 예외로 유지한다.
