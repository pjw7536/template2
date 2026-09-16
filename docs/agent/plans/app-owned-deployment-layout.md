# ExecPlan: 앱별 배포·환경설정 통합

## 목표
- `deploy/<app>/`에서 환경설정, 배포 정의, 운영 문서를 찾을 수 있도록 통합한다.
- 기존 make 진입점과 유효 환경변수·배포 리소스를 유지한다.

## 현재 상태
- env, compose, deploy/k8s에 앱별 파일이 분산되어 있다.
- 이전 작업의 스테이징 변경과 CP1 문서의 미추적 변경이 있다. 현재 작업 파일을 기준으로 이동하고 index는 수정하지 않는다.

## 범위
- Keycloak, Portal, Airflow, Monitoring 배포 파일과 환경설정, 공통 배포 도구, 참조 문서·검증·규칙.
- 앱 업무 소스, 외부 CP1 설정·인증서·DB, 실제 배포, commit/push는 변경하지 않는다.

## 설계
- 앱별 env/compose/k8s/rendered를 필요한 경우에만 둔다.
- Portal의 Nginx와 Monitoring 정적 구성도 해당 앱에 둔다. Airflow 업무 소스는 기존 airflow에 유지한다.
- 공통 Compose 조합·클러스터 설정·env 도구는 deploy/shared에 둔다. Portal 로컬 실행과 Keycloak export는 각 앱의 scripts에 둔다.
- env 원본은 이동만 하고 내용과 권한을 보존한다. CP1 외부 env 경로와 Secret 입력 경계는 유지한다.
- Compose 상대 경로를 조정하고 이동 전후 최종 구성을 비교한다. API/DB/auth 프로토콜 변경은 없다.

## 실행 단계
- [x] 이동 전 env 해시·권한, Compose 및 Kustomize 결과와 index 상태를 확보한다.
- [x] 앱별 파일 이동, 경로 참조와 Git 제외 규칙을 갱신한다.
- [x] 앱 진입 문서와 공통 운영 안내·규칙을 동기화한다.
- [x] 회귀 검사와 이동 전후 비교를 실행하고 결과를 기록한다.

## 검증
- env 내용·권한 및 Git 제외, index 변경 없음 확인.
- dev/oidc/prod/test 및 로컬 DB Compose config 이동 전후 비교.
- Kustomize 진입점 렌더링 이동 전후 비교와 make k8s-export.
- node --test scripts/tests/*.test.cjs, make env-profile-key-check.
- bash scripts/agent/check_compose_configs.sh, npm run agent:test, npm run agent:audit:docs.
- Shell 문법, 변경 문서 링크, 이전 경로 잔존 검사, git diff --check.

## 위험과 대응
- 위험: 상대 경로 변경으로 bind mount나 env 입력이 달라진다.
- 대응: 최종 구성 비교와 실제 참조 파일 존재 검사를 수행한다.
- 위험: 실제 env가 이동 후 Git 대상으로 노출된다.
- 대응: Git 제외 규칙을 먼저 바꾸고 기존 파일 내용·권한을 유지한다.
- 위험: 기존 사용자 변경이 손실된다.
- 대응: 작업 전 파일 스냅샷을 별도 임시 디렉터리에 보관하고 index는 건드리지 않는다.

## 진행 기록
- 2026-09-14: 사용자가 앱별 배포 폴더 통합 제안을 승인했다.

- 2026-09-14: 앱별 env·Compose·Kubernetes·Nginx·Monitoring 설정 이동을 완료했다. 단독 Airflow 정의도 이동하고 기존 진입점의 project_directory를 유지했다.
- 2026-09-14: 현재 문서·Makefile·검사 스크립트·AGENTS 및 관련 skill 경로를 동기화했다. 과거 ExecPlan은 당시 경로를 보존했다.
- 2026-09-14: env·예시·백업 24개의 해시와 권한이 동일하며 실제 운영 env와 백업의 Git 제외를 확인했다. 모든 기존 파일과 스테이징 항목이 보존됐다.
- 2026-09-14: Compose 6개 진입점의 최종 서비스·볼륨·network 구성이 동일하다. 이동한 bind source만 새 경로로 비교했고 x- 원본 템플릿은 최종 runtime 비교에서 제외했다.
- 2026-09-14: Kustomize 6개 결과와 로컬 API 합성 env가 동일하며 생성 YAML 두 개의 Kubernetes 리소스도 동일하다.
- 2026-09-14: 환경설정 테스트 31개, 라우팅·Nginx 컨테이너 테스트 3개, agent 테스트 12개가 통과했다. env profile·Compose 검사, make k8s-render/export, 문서 감사·링크, skill 메타데이터, Shell 문법, git diff --check가 통과했다.
- 2026-09-14: 실제 클러스터 배포와 전체 앱 기동은 수행하지 않았다. Compose host 경로를 외부에서 상대 경로로 지정하는 경우 새 파일 위치 기준을 사용하도록 배포 안내에 명시했다.
