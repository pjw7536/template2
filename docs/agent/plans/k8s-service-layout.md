# ExecPlan: Kubernetes 배포 파일을 서비스별로 정리

## 목표

- Keycloak 배포 파일을 `deploy/k8s/keycloak`에 모은다.
- Portal의 공통 설정, 환경별 설정, migration을 `deploy/k8s/portal`에 모은다.
- Keycloak claim 등록 Job은 사내 OIDC 설정 후 별도 실행한다.

## 현재 상태

- 공통 `base`, `overlays`, `jobs`에 Portal과 Keycloak 파일이 흩어져 있다.
- Keycloak 기동 YAML에 claim 등록 Job까지 포함돼 있다.
- 배포 파일과 관련 문서에 기존 미커밋 변경이 있다.

## 범위

- 배포 파일 이동, 참조 경로, Makefile, 안내 문서, Git 제외 규칙을 갱신한다.
- 기존 앱 코드, 인증 동작, 리소스 이름, 네임스페이스와 볼륨 설정은 유지한다.
- 클러스터에 실제 적용하거나 Git commit/push를 수행하지 않는다.

## 설계

- Keycloak은 overlay 없이 평평하게 유지하며, Portal은 local/internal overlay를 유지한다.
- Keycloak 스택은 claim 스크립트 ConfigMap을 준비하되 Job은 포함하지 않는다.
- 별도 Job YAML에 namespace와 mirror image를 명시해 `kubectl apply -f`로 실행한다.
- 기존 단일 스택 파일명은 유지하고, 별도 Job 배포 파일과 생성 명령을 추가한다.
- 실제 runtime env가 존재하면 내용을 출력하지 않고 이동하며 Git 제외와 권한을 확인한다.

## 실행 단계

- [x] 기존 render 결과를 확보하고 파일을 이동한다.
- [x] Job 실행 분리와 경로 참조, Secret 제외 규칙을 반영한다.
- [x] 처음 사용하는 사람을 위한 폴더 안내와 적용 순서를 문서화한다.
- [x] render 동등성, Job 분리, Shell 문법과 문서 검사를 완료한다.

## 검증

- 모든 기존 Kustomize 진입점의 이동 전후 render를 비교한다.
- Keycloak은 Job 하나만 빠지고 기존 리소스가 동일한지 확인한다.
- 별도 Job이 이전 Job과 같은 namespace/image/Secret/ConfigMap을 참조하는지 비교한다.
- `make k8s-render`, `make k8s-export`, `bash -n`, `git diff --check`, `npm run agent:audit:docs`.
- 기존 경로 잔존 여부와 실제 Secret 파일의 Git 제외·권한을 확인한다.

## 위험과 대응

- 위험: 상대 경로 누락으로 로컬 배포가 깨질 수 있다.
- 대응: 각 환경과 migration의 렌더 결과를 이동 전후 비교한다.
- 위험: 완료된 Job은 단순 apply로 다시 실행되지 않는다.
- 대응: Job 삭제 후 별도 파일 재적용 절차를 문서화한다.
- 위험: 파일 이동으로 실제 credential이 Git 대상이 될 수 있다.
- 대응: 새 경로 Git 제외 규칙을 먼저 추가하고 내용·권한 보존을 검사한다.

## 진행 기록

- 2026-09-11: 사용자가 서비스별 구조와 claim Job 별도 실행을 승인했다.
- 2026-09-11: 원본 38개를 서비스별로 이동하고 실제 runtime env의 권한 600과 Git 제외를 유지했다.
- 2026-09-11: Portal의 4개 환경·migration 진입점은 기존 render와 문자열 단위로 동일했다. Keycloak은 기존 18개 리소스와 독립 Job의 내용이 YAML 구조 비교로 동일했다.
- 2026-09-11: `make k8s-render`, `make k8s-export`, Shell 문법, 전달용 파일 정합성, `git diff --check`와 문서 감사를 통과했다. 실제 클러스터 적용은 수행하지 않았다.
