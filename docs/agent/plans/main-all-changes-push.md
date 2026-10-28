# ExecPlan: 현재 변경 전체 검증과 main 푸시

## 목표
- 사용자가 승인한 현재 staged·unstaged·미추적 변경 전체를 검증한 후 `main`에 커밋하고 `origin/main`에 푸시한다.

## 현재 상태
- 현재 브랜치는 `main`이며 문서 외에 배포 실행 도구·Ingress·환경 설정·회귀 테스트 변경도 포함되어 있다.
- 사용자에게 현재 변경 전체의 커밋·푸시를 명시적으로 승인받았다.

## 범위
- 작업 시작 시 현재 변경 전체 및 이번 Git 마무리 검증 기록.
- 실제 운영 클러스터 적용·원격 강제 푸시·관련 없는 리팩터링은 수행하지 않는다.

## 설계
- 원격 `main`을 fetch해 분기 상태를 확인한다.
- 감사·문서·Web·배포 회귀·렌더 검사를 변경 범위에 맞춰 병렬 실행한다.
- 검증 실패·충돌·인증·브랜치 정책 문제가 있으면 푸시를 중단하고 원인을 보고한다.
- 검증 통과 후 승인된 변경 전체를 stage하고 저장소 커밋 규칙에 맞춰 커밋한다.
- 일반 push 후 로컬·원격 커밋 일치와 작업 트리를 확인한다.
- 후속 수정은 서버 checkout 테스트의 이전 기대값, 비어 있는 이전 디렉터리, 이미 커밋된 코드와 어긋난 hotspot 기준표에 한정한다.
- hotspot 기준은 작업 트리의 새 증가를 허용하지 않는다. HEAD와 동일한 기존 소스임을 먼저 확인하고 커밋된 크기로만 동기화하며 불필요한 예외는 제거한다.

## 실행 단계
- [x] 지침·현재 변경·브랜치·remote 확인
- [x] 원격 최신 상태 확인 및 영향 검토
- [x] 관련 감사·회귀·렌더 검사
- [ ] 검증 결과 기록과 전체 변경 커밋
- [ ] main 푸시 및 결과 확인

## 검증
- `make audit`
- `make tooling-test` 및 `apps/tooling/tests` Python 테스트
- 배포 영역별 Python 회귀 테스트
- `make web-lint`, `make web-test`, `make web-build`
- `make k8s-render`, `make compose-check`, `make env-profile-key-check`
- 변경 스킬 validator, Markdown 상대 링크·색인 검사
- `git diff --check`, 커밋 후 `git status`·원격 SHA 확인

## 위험과 대응
- 모든 현재 변경을 포함하라는 사용자 승인을 적용하되 생성물·무시 파일은 추가하지 않는다.
- 원격 변경은 덮어쓰지 않으며 push 실패 시 강제 푸시하지 않는다.
- 실제 배포 성공과 로컬 정적·회귀 검사 통과를 구분해 보고한다.

## 진행 기록
- 2026-10-28: 사용자 요청에 따라 전체 변경의 검증과 main 푸시를 시작했다.
- 2026-10-28: `git fetch origin main` 성공. `HEAD...origin/main`의 ahead·behind는 모두 0이며 현재 SHA는 `3cf4f96a`다.
- 2026-10-28: 아래 검증 실패로 AGENTS.md의 Git 중단 규칙을 적용했다. 추가 stage·commit·push는 수행하지 않았다.
- 2026-10-28: 사용자가 실패 항목 수정을 요청했다. 세 원인을 수정한 후 재검증하고 앞서 승인한 전체 변경 커밋·푸시를 이어간다.

## 검증 결과와 중단 원인

- `make audit`: 도구 단위 테스트 31개 통과 후 `audit-layout` 실패. root 소유 빈 디렉터리 `apps/web`, `deploy/nginx/default.conf`와 상위 `deploy/nginx`가 남아 있어 구조 위반 3건을 보고했다.
- `make tooling-test`: 93개 중 92개 통과, 1개 실패. `apps/tooling/tests/headlamp-deployment.test.cjs:66`은 checkout 경로에 `docs`를 기대하지만 현재 서버 전용 경로 목록은 `deploy/shared`, `deploy/headlamp`다. 실제 목록과 이전 테스트 기대값이 다르다.
- 이미 실행 중이던 `make -k audit` 결과에서 hotspot 검사도 실패했다. Account 관리자 파일 1,108줄(기준 1,101줄), Activity 테스트 클래스 767줄(기준 756줄), L3 Spider 테스트 파일 1,854줄(기준 1,845줄)이 기준을 초과했다. 제거된 파일·테스트 클래스에 대한 오래된 기준값도 보고했다. 관련 앱 코드는 이번 변경 목록에 없으며 자동 수정하지 않았다.
- `apps/tooling/tests` Python 테스트: 총 43개 중 34개 통과, 실제 Keycloak이 필요한 9개 건너뜀.
- 배포 Python 테스트: 총 159개 중 153개 통과, Helm·공식 chart를 필요로 하는 6개 건너뜀.
- 수정 스킬 4개: validator 통과.
- Web·API 경계, UI, 문서 감사 및 Markdown 상대 링크·anchor 검사: 통과. 새 계획을 색인에 연결했다.
- `git diff --check`: 통과.
- Web 린트·테스트·빌드와 추가 렌더 검사는 위 실패로 Git 마무리를 중단하여 실행하지 않았다.
- 작업 파일은 보존했다. 원인 확인을 위한 읽기와 이 계획·색인 기록 외에 실패 항목을 수정하지 않았다.

## 수정과 재검증

- Headlamp 테스트의 서버 전용 경로 기대값을 현재 계약인 `deploy/shared`, `deploy/headlamp`로 수정했다.
- `rmdir`로 파일이 없는 이전 디렉터리 `apps/web`, `deploy/nginx/default.conf`, `deploy/nginx`만 제거했다. 소스·데이터 파일은 삭제하지 않았다.
- hotspot 초과 세 곳은 작업 트리와 HEAD `3cf4f96a`의 바이트가 동일했다. 증가분은 `40c89918`에 이미 커밋되어 있었으나 기준표는 이전 `fa103b66`에 머물러 있었다. 기준표만 HEAD의 정확한 크기 1,108줄·767줄·1,854줄로 맞췄고 여유분은 추가하지 않았다.
- 기본 한도 이내인 파일 예외 2개와 사라진 클래스 예외 3개를 기준표에서 제거했다. 앱 실행 코드는 변경하지 않았다.

| 검사 | 결과 |
| --- | --- |
| `make audit` | 전체 통과, 감사 도구 테스트 31개 통과 |
| `make tooling-test` | 93개 통과, 실패·건너뜀 없음 |
| 배포 Python 회귀 테스트 | 159개 전부 통과, 이전 Helm 관련 생략 해소 |
| `apps/tooling/tests` Python | 34개 통과, 실제 Keycloak 전용 9개 생략 |
| Airflow 앱 테스트 | 9개 통과, 이미지 내 authlib가 필요한 2개 생략 |
| Web 린트·테스트·빌드 | 통과, 테스트 57개 파일·212개 항목 통과 |
| Kubernetes 렌더·Compose·env 키 검사 | 모두 통과, 운영 클러스터 적용 없음 |
| 변경 Python·shell 문법 | Python 25개·shell 6개 통과 |
| 수정 스킬 4개·Markdown 링크·Git 서식 | 통과 |

- 검증이 완료되어 사용자에게 이미 승인받은 전체 변경의 커밋·푸시를 재개한다. 푸시 후 로컬·원격 SHA와 작업 트리 상태를 최종 응답으로 보고한다.
