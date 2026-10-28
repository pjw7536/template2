# ExecPlan: 저장소 Markdown 정합성 정리

## 목표
- 현재 코드·설정과 다른 문서와 불필요한 중복 안내를 정리한다.

## 현재 상태
- 시작 시 Git 관리 대상과 미추적 Markdown 442개를 확인했다.
- MinIO·Ingress 관련 기존 사용자 변경은 보존한다.
- 상대 Markdown 링크의 파일 누락은 없으나 문서 검사는 ADFS 설정 색인에서 실패한다.

## 범위
- 루트, apps, deploy, local, docs, .codex의 저장소 문서.
- 생성 데이터·외부 의존성 문서는 제외한다. 런타임 코드는 변경하지 않는다.
- 2차 점검에서 확인된 문서 검사 누락은 apps/tooling의 정적 검사와 회귀 테스트로 보완한다.

## 설계
- 현재 안내는 소스·라우트·Makefile과 대조한다.
- 과거 계획·의사결정은 이력으로 보존하고 현재 계약과 구분한다.
- 중복 문서는 현재 안내로 통합하고 참조를 갱신한다.
- API·DB·env 계약 자체는 바꾸지 않는다.

## 실행 단계
- [x] 지침·파일 목록·기존 변경 확인
- [x] 경로·명령·API·설정 및 중복 문서 검토
- [x] 확인된 오류 수정과 불필요한 문서 정리
- [x] 관련 검사 실행 및 결과 기록

## 검증
- `make audit-docs`
- `make audit-tools-test`
- 전체 Markdown 상대 링크 대상 및 현재 안내의 코드 경로 검사
- `git diff --check`

## 위험과 대응
- 과거 기록을 현재 계약으로 오인하지 않도록 별도 안내한다.
- 삭제는 대체 문서와 참조 여부를 확인한 파일에 한한다.
- 사용자 변경 파일에는 필요한 문서 수정만 추가한다.

## 진행 기록
- 2026-10-27: 전체 문서 목록과 초기 검사 결과 확인.

- 2026-10-27: Auth·Account의 제거된 직접 ADFS callback, DB 권한 승인 API와 관리자 안내를 Keycloak 세션 계약으로 교체했다. Emails의 과거 superuser 우회 설명도 수정했다.
- 2026-10-27: 모듈의 단일 Python 파일 경로를 현재 패키지 경로로 수정하고 누락된 Spider·접속 통계 route를 색인에 추가했다.
- 2026-10-27: 운영 env의 Git 관리 여부를 `.gitignore`·실제 추적 파일·배포 안내와 대조해 수정했다. credential 값은 읽거나 문서에 복제하지 않았다.
- 2026-10-27: 현재 PM SPIDER 명세와 충돌하고 참조가 없는 `docs/agent/pm-comparison-reimplementation-brief.md`를 삭제했다. 현재 데이터 명세와 과거 ExecPlan·결정 이력은 보존했다.

## 검증 결과와 한계

- `make audit-docs`: 통과. 제거된 `ADFS_*`는 지원 설정이 아닌 이전 계약이라는 설명을 색인에 남겼다.
- `make audit-tools-test`: 27개 테스트 통과.
- 작업 시작·종료 시 Markdown 442개: 오래된 브리프 1개 삭제, 이 실행 기록 1개 추가.
- 전체 Markdown 상대 파일 링크 검사: 누락 0개.
- 현재 문서의 명시적 저장소 코드 경로 검사: 남은 후보는 스킬의 금지 경로·가상 예시이며 실제 파일 안내 오류가 아니다.
- 현재 안내의 `make <target>` 대조: 없는 `portal-up`은 원문이 명시적으로 부재를 설명하므로 유지했다.
- `git diff --check`: 통과.
- 문서만 수정했으며 운영 클러스터·외부 서비스의 현재 상태나 모든 API의 실동작을 검증한 결과는 아니다. 과거 계획은 작성 시점의 기록으로 보존했다.

## 2차 정밀 점검

사용자의 추가 요청에 따라 본문을 API view·serializer·배포 script와 대조한다.

- [x] API method·권한·응답·payload와 누락 endpoint 점검
- [x] 실행 명령과 배포·환경 문서 간 모순 점검
- [x] 에이전트 지침·스킬의 현재 계약 및 중복 문서 점검
- [x] 관련 검사와 수정 근거 기록

- 2026-10-27: 기존 문서 검사기가 여러 줄·단일 따옴표 route를 누락하고 다른 모듈의 문자열로도 통과시키는 문제를 확인했다. AST로 모듈별 색인 누락·제거 경로를 검사하도록 도구를 보완한다.


## 2차 수정 근거와 결과

- API: 공통 `api.common.permissions`와 DRF 기본 permission을 대조해 Observer·AppStore·VOC·Activity의 익명·앱 접근 안내를 수정했다.
- 실제 view 메서드와 대조해 Drone의 대상·매핑·수신자·수신자 권한 API를 바로잡았다. 테이블 수정 허용 컬럼은 `comment`, `needtosend`이며 기간 입력은 `recentHoursStart/End`다.
- 모든 도메인 `urlpatterns`를 AST로 대조해 Assistant 평가·내보내기·요약, Drone 옵션, Data Movement 요약, L3 trend·제외 조건, Observer evidence 경로를 색인에 반영하고 제거된 Observer endpoint를 삭제했다.
- 새 API 문서 `docs/api/l0-spider.md`, `pm-spider.md`, `tttm-spider.md`는 현재 view·serializer·service를 기준으로 작성하고 색인에 연결했다. TTTM의 입력 허용과 실제 전달 여부도 구분했다.
- Assistant 일반 Profile이 shared만 읽는다는 registry 계약과 표준 Turn SSE event를 반영했다. Health가 DB readiness 검사를 수행한다는 오해를 수정했다.
- `purge_drone_sop --dry-run`은 미지원이므로 인자 없는 안전한 조회 예시로 수정했다. 전체 명령 예시의 옵션을 management command와 배포 Python parser의 정의와 대조했다.
- `requirements.txt` 기준 Django 버전을 수정하고 MinIO API 접속 키·서버 관리자 계정의 역할을 구분했다. 과거 READINESS 결과는 당시 기록임을 명시했다.
- 끊어진 section anchor 2개를 수정했다. 현재 문서의 남은 경로 후보는 상대 script 경로, 선택 파일, 가상 예시·생성 산출물이다.
- 스킬의 service facade 실행 로직 지침·임의 URL 모듈 안내를 API AGENTS.md에 맞췄다. 레이아웃 예시의 grid 공백 표기와 sticky scroll owner를 수정했다. Web AGENTS.md에도 root와 route의 높이 소유 규칙을 명확히 했다.
- `apps/tooling/agent/check_docs_routes.py`를 추가해 실제 모듈 행의 누락·삭제 경로를 검사한다. 기존 bash 검사의 한 줄·큰따옴표 제한과 지원 종료된 ADFS 필수 그룹을 제거했다.
- `make audit-docs`: 통과. AST 기준 모든 backend 모듈 endpoint 색인 일치.
- `make audit-tools-test`: 31개 통과(기존 27개 + URL 색인 회귀 4개).
- `node --test apps/tooling/tests/app-layout.test.cjs`: 5개 통과.
- 수정한 스킬 4개는 `skill-creator/scripts/quick_validate.py` 통과.
- Markdown 445개의 상대 파일 링크와 현재 안내의 section anchor 검사: 누락 0개. 동일 내용의 중복·빈 Markdown 없음.
- `bash -n apps/tooling/agent/check_docs_inventory.sh`, `git diff --check`: 통과.
- 추가 구조 검사에서 빈 옛 경로 `apps/web`과 `deploy/nginx/default.conf`를 발견했다. `apps/web`은 `rmdir`로 제거했다.
- `deploy/nginx/default.conf`와 상위 `deploy/nginx`는 root 소유이고 하위 디렉터리 삭제 권한이 없어 남아 있다. `sudo -n rmdir`도 비밀번호가 필요해 실패했다. 따라서 `make audit-layout`의 남은 실패는 `deploy/nginx: 앱 목록에 없는 소유 디렉터리` 1건이다. 내용이 없는 디렉터리이며 실제 파일은 없다. 관리자 권한으로 `sudo rmdir deploy/nginx/default.conf deploy/nginx` 실행이 필요하다.
- 앱 실행 코드와 기존 MinIO·Ingress 사용자 변경은 수정하지 않았다. 운영 클러스터 변경·실동작 검증은 수행하지 않았다.

## 빈 디렉터리 후속 정리

- 2026-10-27: 사용자 요청에 따라 로컬 Docker의 root 사용자로 `rmdir`를 실행해 빈 `deploy/nginx/default.conf`와 `deploy/nginx`를 제거했다. 위 권한 부족으로 남았던 항목은 해결됐다.
- `make audit-layout`: 통과. 앱 소유 경로·서버 의존·이전 소스 경로 위반 없음.
