# 서버 배포 지침

## 소유권과 실행 경계

- `deploy/<app>`은 준비된 이미지·chart의 설치·운영 env·Kubernetes 정의를 소유한다. 제품 코드와 Airflow DAG·플러그인은 `apps/<app>`, 외부 PC 설정·mock·실행 도구는 `local/<app>`, CI Compose·test 입력은 deploy가 소유한다.
- 사내 서버 배포는 Kubernetes만 지원한다. 정의가 없으면 전환 미완료로 표시하고 Compose 검증으로 대신하지 않는다.
- 정적 검사(`make server-check`)는 local·앱 소스·루트 docs 없이 실행되어야 한다. 이미지 tag 계산·빌드와 그 tag를 쓰는 배포·대조는 `apps/` 소스가 있는 저장소 전체 checkout에서 실행한다. 공통 정의는 `shared` 또는 앱별 base에 두고 local에서 재사용한다. 다른 앱에 설정을 복제하지 않는다.
- 진입점은 루트 Makefile, 앱·그룹 원본은 [apps.json](shared/apps.json), 파일 준비는 [서버 파일 받기](shared/docs/operations/01-checkout.md)다.

## 탐색과 문서

- 대상 앱 README → 작업별 설치·운영 문서 → 관련 manifest·env·script → 필요한 shared 계약 순으로 확인한다.
- 인프라 정보의 분류·확인 상태·갱신은 [인프라 README](shared/docs/infrastructure/README.md)와 [하위 지침](shared/docs/infrastructure/AGENTS.md)을 따른다. 실제 설정 원본은 소유 앱 manifest·env·Helm values이며 운영값을 다른 안내에 복제하지 않는다. 비밀값은 문서에 쓰지 않는다.
- 정적 검사와 실제 서버 적용·접속 성공을 구분하고, 정보 기록 요청을 서버 적용 요청으로 확대하지 않는다.
- 배포 문서는 사람과 사내 운영 agent가 함께 읽는 한 벌이다. 같은 절차를 두 곳에 쓰지 않는다. `.opencode/skills/`의 스킬은 읽는 순서와 보고 형식만 두고 절차를 복제하지 않는다.
- 진입점은 [배포 가이드](README.md)(공통 규칙·단계 표시·공통 절차)와 [공통 색인](shared/docs/README.md)이다. 공통 절차는 `shared/docs/{kubernetes,ingress,certificates,operations,configuration}/`, 현재 운영 정보는 `infrastructure/`에서 관리한다.
- `shared/ingress`는 실행 코드·manifest, `shared/certs`는 인증서·CA 파일을 소유한다. 상세 절차는 공통 문서에 둔다.
- 앱 README는 앱 가이드이며 모든 앱이 같은 절을 같은 순서로 가진다: `한눈에 보기` → `구성` → `사람이 하는 일` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `문제 해결과 멈춤 조건` → `상세 문서`. 가이드에는 IP 주소와 대화형 입력(`read`)을 쓰지 않고 `KUBE_CONTEXT="<context>"`를 쓴다.
- `<app>/docs/`에는 가이드에 없는 내용만 둔다(입력 키 설명, 사람이 하는 일의 방법, 백업·교체·이전 같은 운영 작업). 가이드의 설치·업데이트 단계를 다시 풀어 쓰지 않는다. 파일은 `01-<역할>.md`처럼 두 자리 연속 번호와 역할 이름을 쓰고 짧은 참고만으로 파일을 늘리지 않는다.
- 운영 agent가 실행하는 단계와 명령 블록에는 [조회]·[검사]·[변경]·[승인]을 표시한다(뜻은 [배포 가이드](README.md#단계-표시)). agent는 표시가 있는 단계만 실행하므로 사람이 하는 작업에는 표시를 두지 않는 것이 기본이다.
- [사람]은 agent가 실행할 수 없어 멈춰야 하는 자리에만 쓴다: 다른 서버·PC·관리 화면에서 하는 작업이나 숨김 입력·터미널 점유 명령이 agent 단계와 한 절에 섞여 있을 때, 권한으로 막힌 삭제, 가이드 `B. 업데이트` 표에서 사람이 할 행. 관리 호스트에서 agent가 실행할 수 있는 작업은 판단이 필요해도 [사람]으로 두지 않고, 사람에게 받을 입력을 적은 뒤 [변경] 또는 [승인]으로 쓴다. 가이드 `사람이 하는 일` 표의 행과 사람 작업만 있는 절에는 붙이지 않는다.
- Job·overlay·입력 템플릿 옆 README는 원본의 역할·사용 조건·상세 절차 링크만 설명하고 전체 명령을 반복하지 않는다.
- 절차에는 실행 위치·입력·명령·성공 문구·실패 시 조치를 명시한다. [변경]·[승인] 단계에는 agent가 결과를 확인할 성공 문구나 뒤따르는 [조회]·[검사] 명령을 반드시 둔다. 단계마다 명령은 하나의 블록으로 두고 성공을 판단할 출력 문구를 적는다. 문서 번호는 권장 읽기 순서이며 본문의 단계 번호나 실행 파일 번호와 구분한다. 공통 문서는 주제별 역할 이름을 유지한다.
- 문서 이동 시 내부 링크·도구 안내 경로를 갱신한다. 이전 경로·앵커 호환 안내는 보존 요청이 있을 때만 둔다.

## 환경과 데이터 계약

- 승인된 사내 패키지·driver artifact URL만 서버 전용 빌드 입력에 고정할 수 있다. 버전 명시, credential·사용자별 endpoint가 아님, local 미사용, `docs/reference/01-configuration.md` 문서화 조건을 모두 만족해야 한다. 그 외 URL·credential은 루트 env 원칙을 따른다.
- 새로 추가·변경하는 API 업무 파일의 컨테이너 경로는 `/data/<domain>`이며 domain은 lowercase snake_case다. Django는 `<DOMAIN>_DATA_ROOT`를 노출하고 개별 파일이 원본 계약일 때만 `<DOMAIN>_<NAME>_PATH`를 쓴다.
- 참고·원본 데이터는 Kubernetes `readOnly: true`, 업로드·생성물·처리 큐 등 앱 소유 데이터만 쓰기를 허용한다.
- Worker의 앱 소유 호스트 경로는 `/appdata/<app 또는 domain>`이다. 설정 가능한 경로는 env로 유지하고 기존 공유 경로를 재사용한다. kubelet·container runtime·node-exporter 시스템 경로와 동적 StorageClass 저장 위치는 이 통일 규칙의 대상이 아니며 컨테이너 경로와 구분한다.
- 기존 PV·데이터를 자동 이동·삭제하지 않는다. 경로 변경에는 백업·데이터 이전·PV/PVC 전환을 별도로 준비한다.
- Compose 마운트는 `${<DOMAIN>_DATA_HOST_PATH:-../../../data/<domain>}`와 읽기 전용 `:ro`를 적용한다. 외부 PC kind 호스트 매핑은 local overlay에 명시한다.
- API 마운트 변경은 `portal/k8s` base·운영 overlay, `local/portal/k8s`, `local/shared` 호스트 매핑, 양쪽 Portal env, `docs/reference/01-configuration.md`를 함께 맞춘다. 이는 전체 개발 checkout의 동기화 규칙이며 서버 실행의 local 의존성을 뜻하지 않는다.

## 사내 운영 agent

사내 관리 호스트의 opencode `ops` agent([정의](../.opencode/agents/ops.md))는 저장소 전체 checkout 하나에서 이미지를 빌드하고 배포·운영하며 저장소를 개발하지 않는다. 루트 지침의 개발 규칙은 적용하지 않는다. 사람 승인·입력 없이 끝까지 진행하는 것이 기본이다.

- 코드·manifest·env 원본·스크립트·스킬·지침을 수정하지 않는다. 원인이 저장소에 있으면 보고하고 그 앱만 중단한다. 수정 가능 범위는 `shared/docs/infrastructure/`의 운영값·확인 상태·pending·별칭 표이며 커밋은 사람이 한다. checkout 갱신은 `git pull --ff-only`만 사용한다.
- 권한: shell은 기본 허용이고 삭제(namespace·PV·CRD·`helm uninstall`)와 이력을 바꾸는 Git 명령만 거부한다. env·Secret은 진단에 필요하면 읽을 수 있으나 비밀값을 응답·운영 기록에 옮겨 적지 않는다. 승인 대기(`ask`) 규칙은 두지 않는다.
- 단계 표시: [조회]·[검사]·[변경]은 바로 실행한다. [승인]은 되돌릴 수 없거나 서비스가 중단되는 변경에만 쓴다. DNS·인증서 발급·방화벽·사내 계정 발급·제어면과 노드 설정처럼 클러스터 밖의 일은 가이드의 `사람이 하는 일` 표에 완료 확인 명령과 함께 적는다.
- 운영 agent는 요청 종류마다 스킬(`.opencode/skills/`) 하나로 시작한다: 배포·갱신 `server-deploy-routine`, 장애 확인 `incident-triage`, 설치 준비 점검 `server-readiness-check`, 저장소와 서버 대조 `deploy-drift-check`, 외부 전달용 상태 보고 `server-state-report`, 인프라 기록 갱신 `infra-record-sync`. 스킬은 이 폴더의 문서를 절차의 원본으로 가리키고 명령 블록을 두지 않는다. 스킬을 추가하면 [agent 정의](../.opencode/agents/ops.md)의 사용 권한과 요청별 스킬 표, `test_deploy_guides.py`의 `SKILL_SOURCES`를 함께 고친다. 요청 유형이 기존 스킬과 겹치는 스킬은 만들지 않는다. 판정 원본은 [배포 상태 대조](shared/docs/operations/04-drift.md)와 `shared/scripts/deploy_state.py`다.
- 모든 앱은 `make <app>-check`, `make <app>-up`, `make <app>-smoke`를 제공한다. 의존 관계·기본 env·배포 단계·smoke 경로의 원본은 [apps.json](shared/apps.json)이며 `make ops-deploy APP=<app>`이 그 `steps`를 실행하고 대조까지 수행한다.
- 앱의 배포 명령·순서·성공 문구·사람 작업을 바꾸면 같은 변경에서 그 앱 가이드(`<app>/README.md`)를 갱신한다. 새 수동 단계가 필요하면 가이드에 사람 작업을 늘리지 말고 `<app>-up` 또는 `steps`에 넣는다.
- 사내 빌드 이미지(Airflow·Portal)는 `make <app>-image`가 이 checkout에서 빌드해 사내 이미지 저장소로 push하고 `steps`의 첫 단계로 둔다. tag는 소스 tree와 build env 내용으로 자동으로 정하며(`shared/scripts/image_registry.py`의 `source_tag`), registry에 같은 tag가 있으면 빌드하지 않는다. tag를 저장소 파일에 직접 쓰게 만들지 않는다. 빌드 도구는 `make build-tools-install`이 설치한다.
- 외부로 전달하는 내용에는 서버명·IP·사내 도메인을 쓰지 않는다. [별칭 표](shared/docs/infrastructure/aliases.json)의 별칭만 쓰고 `make ops-report`·`make ops-redact`의 출력만 전달한다. 가이드·스킬·agent 정의에는 IP를 적지 않는다.
- `KUBE_CONTEXT`를 항상 명시한다. 배포 전 `make ops-preflight`, 배포 후 `ops-deploy` 요약의 `driftResultCode`가 0인지 확인한다. `make <app>-up`이 아닌 명령으로 배포했으면 `make deploy-record`로 기록한다.

## 검증

- 배포 문서: `python3 -m unittest discover -s apps/tooling/tests -p 'test_deploy_guides.py'`(모든 앱 가이드의 고정 절·일괄 배포와 smoke 명령·Makefile 타깃·IP 미포함, `deploy/`와 `.opencode/` 전체의 링크·앵커, agent 권한 정의).
- 운영 자동화 도구: `python3 -m unittest discover -s deploy/shared/tests -p 'test_ops_tools.py'`(폴더 준비·관리자 인증·smoke·일괄 배포·별칭 치환·이미지 빌드·push·`apps.json`의 `steps`와 Makefile 일치).
- 배포 기록·대조 도구: `python3 -m unittest discover -s deploy/shared/tests -p 'test_deploy_state.py'`. 앱을 추가하면 `apps.json`의 `dependsOn`·`env`·`steps`·`smoke`·`runtime.namespace`(공유 namespace는 `selector`)를 함께 정한다.
- 배포 정의: 루트 `make server-check APP=<app> PROFILE=prod`. 실제 입력·클러스터 조회·적용·접속은 별도로 보고한다.
- 문서: 상대 링크·앵커, `git diff --check`, `make audit-docs`. 이동 시 삭제 경로·앵커 참조와 정보 보존을 확인한다.
- 공통 경로·도구 변경과 문서 이동: 전체 개발 checkout에서 `node --test apps/tooling/tests/server-checkout.test.cjs`로 서버 독립 실행을 확인한다.
- 보고에는 변경 내용·검증 결과와 실제 서버 조회 여부·남은 확인을 구분한다.
