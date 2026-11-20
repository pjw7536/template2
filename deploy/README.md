# 서버 배포

사내 Kubernetes 클러스터에 앱을 설치·운영하는 안내입니다. 사람과 사내 운영 agent(opencode `ops`)가 같은 문서를 봅니다.
명령은 관리 호스트의 저장소 전체 checkout 루트에서 실행합니다. 서버·주소·적용 상태의 원본은 [사내 인프라 정보](shared/docs/infrastructure/README.md)입니다.

- [문서 읽는 법](#문서-읽는-법)
- [실행 규칙](#실행-규칙)
- [앱 설치 순서](#앱-설치-순서)
- [모든 작업 공통 시작](#모든-작업-공통-시작)
- [공용 TLS 등록](#공용-tls-등록) · [사내 CA 묶음](#사내-ca-묶음) · [공용 Traefik 검사·갱신](#공용-traefik-검사갱신) · [이미지 빌드 도구](#이미지-빌드-도구)
- [설치 준비 점검](#설치-준비-점검)
- [배포 후 공통 마무리](#배포-후-공통-마무리)
- [장애 조회](#장애-조회)
- [공통 절차와 기록](#공통-절차와-기록)

## 문서 읽는 법

| 문서 | 내용 |
| --- | --- |
| 이 문서 | 모든 앱에 공통인 규칙과 절차 |
| `deploy/<app>/README.md` | 앱 가이드. 모든 앱이 같은 순서의 절을 가집니다: `한눈에 보기` → `구성` → `사람이 하는 일` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `문제 해결과 멈춤 조건` → `상세 문서` |
| `deploy/<app>/docs/` | 가이드에 없는 상세: 입력 키 설명, 사람이 하는 일의 방법, 백업·교체·이전 같은 운영 작업 |
| [공통 절차](shared/docs/README.md) | 클러스터 구축, Traefik·VIP, 인증서, checkout, 배포 상태 대조 |
| [사내 인프라 정보](shared/docs/infrastructure/README.md) | 서버·주소·저장소·운영 위치와 [서버 적용 대기 작업](shared/docs/infrastructure/pending.md), 외부 전달용 [별칭 표](shared/docs/infrastructure/aliases.json) |

### 단계 표시

운영 agent가 실행하는 단계에는 무엇을 하는 단계인지 표시합니다. 사람이 하는 작업은 따로 표시하지 않는 것이 기본이며, agent가 멈춰야 하는 자리에만 [사람]을 붙입니다.

| 표시 | 뜻 | 운영 agent의 행동 |
| --- | --- | --- |
| [조회] | 클러스터·파일을 읽기만 함 | 바로 실행 |
| [검사] | 입력·원본을 검사하고 클러스터를 바꾸지 않음 | 바로 실행. 실패하면 오류 문구의 조치를 따름 |
| [변경] | 클러스터·서버를 바꿈 | 바로 실행. 실행한 명령과 결과를 보고에 남김 |
| [승인] | 되돌릴 수 없거나 서비스가 중단되는 변경 | 명령·대상·영향을 보여 주고 사용자 승인 후 실행 |
| [사람] | 운영 agent가 실행할 수 없는 일이 agent 단계 사이에 있을 때: 다른 서버·PC·관리 화면에서 하는 작업, 숨김 입력이나 터미널을 점유하는 명령, 권한으로 막힌 삭제 | 실행하지 않음. 그 자리에서 멈추고 할 일을 요청하거나, 사람이 끝냈는지 확인한 뒤 다음 단계로 감 |

표시가 적용되는 범위는 다음과 같습니다.

- 단계 번호 뒤나 명령 블록 바로 앞 문장의 표시는 그 단계의 명령 전체에 적용됩니다.
- `모두 [조회]입니다`라고 쓴 절은 그 절의 모든 명령이 [조회]입니다.
- 앱 가이드 `사람이 하는 일` 표의 일은 표시가 없어도 사람이 합니다. `완료 확인` 칸의 명령은 [조회]입니다. 운영 agent는 확인 명령으로 완료 여부를 먼저 조회하고, 미완료일 때만 할 일을 요청합니다.
- 앱 가이드 `B. 업데이트` 표의 실행 칸은 [승인]·[사람]·`멈추고 사람에게 묻기`가 적혀 있지 않으면 [변경]입니다.
- 그 밖에 표시가 없는 절과 명령 블록은 사람이 직접 작업할 때의 방법이거나 설명입니다. 운영 agent는 실행하지 않습니다. 상세 문서(`deploy/<app>/docs/`)의 다른 서버 작업·관리 화면 조작·수동 복구가 여기에 해당합니다.

명령의 `<...>`는 실제 값으로 바꿉니다.

| 자리표시 | 값을 찾는 곳 |
| --- | --- |
| `<context>` | 사용자가 지정한 값, 없으면 [운영 위치](shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)의 서버 기본 context. `kubectl config get-contexts`에 있는 이름이어야 함 |
| `<app>` | [apps.json](shared/apps.json)의 앱 이름 하나 |
| `<namespace>` | 앱 가이드의 `한눈에 보기` 표 |
| `<APP VIP 주소>` | [별칭 표](shared/docs/infrastructure/aliases.json)의 `VIP-APP` |

## 실행 규칙

1. 실행 위치는 관리 호스트의 저장소 루트입니다. `pwd`가 저장소 루트이고 `Makefile`이 있는지 확인합니다.
2. 모든 명령에 `KUBE_CONTEXT="<context>"`를 붙입니다. `kubectl config use-context`를 쓰지 않습니다.
3. 명령마다 새 셸이 열릴 수 있으므로 `export`한 변수에 의존하지 말고 값을 명령에 직접 씁니다. 외부 env·chart 경로를 쓰면 검사·배포·대조의 각 명령에 같은 입력을 붙입니다.
4. 처음 설치와 업데이트 모두 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`가 기본입니다. [apps.json](shared/apps.json)의 `steps`를 순서대로 실행하고 [배포 상태 대조](shared/docs/operations/04-drift.md)까지 수행합니다. 모든 앱은 단계별 타깃 `make <app>-check`, `make <app>-up`, `make <app>-smoke`도 제공합니다.
   - 한 번에 앱 하나만 받습니다. `APP`을 빼면 실행되지 않습니다. 앱 가이드가 요구하는 추가 입력(예: `FTP_NODES=...`)은 같은 명령 뒤에 붙이면 모든 단계에 전달됩니다.
   - 결과는 `{"app":`으로 시작하는 JSON 한 줄입니다. `"failedStep": null`이고 `"driftResultCode": 0`이면 성공입니다. 실패하면 `failedStep`이 멈춘 단계 이름이고 그 뒤에 make 오류 줄이 붙습니다.
   - 다시 실행해도 됩니다. 이미 있는 리소스와 이미 올린 이미지는 건너뛰지만, `<app>-up`은 Pod를 다시 시작할 수 있습니다.
5. [변경]·[승인] 단계를 실행한 뒤에는 그 단계에 적힌 성공 문구나 바로 뒤의 확인 명령으로 결과를 확인하고, 확인한 출력의 핵심 줄을 보고에 남깁니다. 성공 문구가 적혀 있지 않으면 `make <app>-smoke`와 [조회] 명령으로 확인합니다. 확인하지 못한 변경을 완료로 보고하지 않습니다.
6. 단계가 실패하면 앱 가이드의 `문제 해결과 멈춤 조건`에서 같은 오류를 찾습니다. 조치가 적혀 있으면 한 번 수행하고 같은 명령을 다시 실행합니다. 다시 실패하거나 멈춤 조건에 해당하거나 가이드에 없는 오류면 그 앱만 멈추고 실패한 명령·종료 코드·오류 마지막 20줄을 보고합니다.
7. 여러 앱을 요청받으면 [앱 설치 순서](#앱-설치-순서) 표의 순서대로 앱마다 공통 시작부터 마무리까지 반복합니다. 한 앱이 멈추면 그 앱을 먼저 필요로 하는 앱만 건너뛰고 나머지를 계속한 뒤 앱별 결과를 함께 보고합니다.
8. 비밀번호·토큰·개인키 값을 응답·운영 기록·보고서에 옮겨 적지 않습니다. env 파일과 Secret은 진단에 필요하면 읽을 수 있습니다.
9. 사내망 밖으로 전달하는 내용에는 서버 IP·서버명·사내 도메인을 쓰지 않습니다. [서버 상태 보고](shared/docs/operations/04-drift.md#서버-상태-보고)의 `make ops-report` 출력만 전달합니다.

### 하지 않는 일

- PV·PVC·namespace·CRD·DB·Worker 데이터 폴더를 삭제·이동하지 않습니다. `helm uninstall`, `kubectl delete namespace`, `kubectl drain`을 실행하지 않습니다.
- `kubectl apply -k deploy/shared/ingress`와 렌더 결과 파일(`deploy/*/rendered/*.yaml`) 직접 적용을 하지 않습니다. 공용 Traefik의 감시 namespace와 VIP 배치가 기본값으로 돌아갑니다.
- `make k8s-env APP=keycloak ...`을 실행하지 않습니다. 기존 Keycloak Secret을 덮어씁니다.
- Portal overlay를 `kubectl apply -k`로 직접 적용하지 않습니다. 이미지 tag가 `auto`로 남습니다.
- 운영 agent는 저장소 파일(코드·manifest·env·스크립트·문서)을 수정하지 않습니다. 예외는 `deploy/shared/docs/infrastructure/`의 운영 기록뿐이며, 검사를 통과시키려고 파일을 고치지 않습니다.

## 앱 설치 순서

의존 관계의 원본은 [apps.json](shared/apps.json)의 `dependsOn`입니다. 모든 앱은 공용 Traefik과 해당 host의 공용 TLS가 먼저 필요합니다.

| 순서 | 앱 | 먼저 필요한 것 |
| --- | --- | --- |
| 1 | 공용 Traefik·TLS (이 문서) | Ready Worker, 인증서 파일 |
| 2 | [Keycloak](keycloak/README.md) | Traefik, TLS |
| 3 | [MinIO](minio/README.md), [Registry](registry/README.md) | Traefik, TLS |
| 4 | [Airflow](airflow/README.md) | Keycloak, Registry, TLS, 빌드 도구 |
| 4 | [Monitoring](monitoring/README.md) | Traefik, TLS |
| 4 | [Headlamp](headlamp/README.md) | Keycloak, 제어면 API server OIDC |
| 4 | [FTP](ftp/README.md) | 대상 노드·방화벽 |
| 5 | [Portal](portal/README.md) | Keycloak, MinIO, Registry, 외부 PostgreSQL, 빌드 도구 |

클러스터와 관리 호스트가 아직 없다면 [공통 절차](shared/docs/README.md)의 클러스터 구축과 [관리 호스트 준비](shared/docs/operations/04-drift.md#관리-호스트-준비)를 먼저 합니다.

## 모든 작업 공통 시작

1. [변경] checkout 갱신. `git pull`이 실패하면 현재 checkout으로 진행하고 실패를 보고에 남깁니다.
   ```bash
   git pull --ff-only
   git status --short
   git log -1 --oneline
   ```
   대상 배포 경로(`deploy/<app>`)나 소스(`apps/<app>`)에 미커밋 변경이 있으면 그 앱은 멈추고 보고합니다.
2. [조회] context와 노드를 확인합니다. 선택한 context 이름이 목록에 없거나 노드 조회가 실패하면 kubeconfig 문제이므로 멈춥니다.
   ```bash
   kubectl config get-contexts
   kubectl --context "<context>" get nodes
   ```
3. [검사] 반입물과 입력을 확인합니다. 준비 상태만 요청받으면 이 결과를 보고하고 끝냅니다.
   ```bash
   make ops-preflight APP=<app> PROFILE=prod KUBE_CONTEXT="<context>"
   ```
   `배포 차단`이면 표시된 파일·키를 확인합니다. chart 파일 누락이면 [변경] 그 앱의 chart 받기(`make airflow-fetch-chart`, `make monitoring-fetch-chart`, `make headlamp-fetch-chart`)를 한 번 실행하고 사전 검사를 다시 합니다. 사내 미러에서 받지 못하면 반입이 필요하므로 그 앱을 멈추고 필요한 파일 이름을 보고합니다. `현장 확인 필요`는 안내이며 배포를 막지 않습니다.
4. [조회] 현재 상태를 대조합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```
   JSON의 `resultCode`와 `apps[].findings`를 읽습니다. 0은 일치, 1은 불일치·경고, 2는 판정 불가입니다. `배포 기록 없음`이고 namespace에 워크로드가 없으면 앱 가이드의 A(최초 설치), 그 밖에는 B(업데이트)입니다. 유효한 JSON이 없으면 kubeconfig·context 문제이므로 멈춥니다.

## 공용 TLS 등록

[사람] 인증서 발급과 PFX 추출은 사람이 하고([인증서 준비](shared/docs/certificates/prepare.md)), 파일(`fullchain.crt`, `private.key`)을 `deploy/shared/certs/<사이트>/`에 둡니다.

[조회] 파일이 있는지 확인합니다. 없으면 배치를 요청하고 그 host를 쓰는 앱을 멈춥니다.

```bash
ls -l deploy/shared/certs/<사이트>/fullchain.crt deploy/shared/certs/<사이트>/private.key
```

[변경] host마다 한 번씩 등록합니다. SAN 인증서 하나를 여러 host가 함께 써도 host마다 반복합니다. 이미 같은 인증서가 등록돼 있으면 변경 없이 끝납니다.

```bash
make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=<공개 host> TLS_CERT_FILE="$PWD/deploy/shared/certs/<사이트>/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/<사이트>/private.key"
```

성공: `공용 TLS 등록 완료: <host>`. 실패: SAN에 host가 없거나 체인·만료 문제이므로 그 host를 쓰는 앱을 멈추고 인증서 재발급을 요청합니다. 상세는 [인증서 적용](shared/docs/certificates/apply.md)에 있습니다.

## 사내 CA 묶음

Keycloak OIDC를 검증하는 앱(Airflow·Headlamp), 관리 API 도구, smoke가 사용합니다. 사람이 `deploy/shared/certs/ca/`에 사내 Root·Issuing CA 파일을 둔 뒤 한 번 실행합니다.

[변경]
```bash
make ca-bundle CA_HOST=sso.etch.samsungds.net
```

성공: `CA 묶음 준비 완료: deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`. CA 파일이 없다는 오류면 파일 배치를 요청합니다.
이 명령은 묶음을 CA 폴더의 현재 내용으로 다시 만듭니다. CA를 교체했으면 다시 실행한 뒤 묶음을 쓰는 앱(Airflow의 OIDC CA ConfigMap, Headlamp의 `headlamp-oidc-setup`)을 갱신합니다.

## 공용 Traefik 검사·갱신

배치(VIP backend)를 바꾸지 않는 일반 갱신입니다. 최초 구성과 backend 확장은 [Traefik 셋업](shared/docs/ingress/setup.md)에 있습니다.

1. [검사]
   ```bash
   make ingress-check KUBE_CONTEXT="<context>"
   ```
   성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`
2. [변경] 공용 Traefik이 없거나, 앱 가이드가 `ingress-up`을 요구하거나, 검사가 공용 TLS 마운트 누락을 알릴 때 실행합니다.
   ```bash
   make ingress-up KUBE_CONTEXT="<context>"
   kubectl --context "<context>" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
   ```
   성공: `공용 Ingress 준비 완료`, Traefik Pod `1/1 Running`.

[승인] backend 노드 추가·변경(`VIP_BACKENDS` 지정)은 서비스 진입 경로를 바꾸므로 사용자에게 값과 승인을 받습니다. 기존 backend를 빼지 않습니다.

## 이미지 빌드 도구

Airflow·Portal 이미지는 이 checkout에서 빌드해 사내 이미지 저장소로 push합니다. `make ops-deploy`의 첫 단계(`<app>-image`)가 수행하며 nerdctl·BuildKit이 필요합니다.

1. [검사]
   ```bash
   make build-tools-check
   ```
   성공: `빌드 도구 준비 완료`.
2. [변경] 도구가 없다고 나오면 설치합니다. 비밀번호 없는 sudo가 필요하고 containerd는 재시작하지 않습니다.
   ```bash
   make build-tools-install
   ```
   성공: `빌드 도구 준비 완료`. `비밀번호 없는 sudo 권한이 필요합니다`면 사람에게 이 명령의 실행 또는 sudo 권한을 요청합니다. 다운로드 실패면 메시지에 나온 폴더로 릴리스 파일 반입을 요청합니다.

이미지 tag는 소스 내용으로 자동으로 정해지고, registry에 같은 tag가 있으면 빌드하지 않습니다. 저장소 파일의 tag를 고칠 필요가 없습니다.
push에는 [Registry](registry/README.md)가 먼저 배포돼 있어야 하고, 관리 호스트가 저장소 주소의 인증서를 신뢰해야 합니다. 설치 내용과 수동 절차는 [빌드 도구 준비](airflow/docs/02-artifacts.md#containerd-빌드-도구-준비)에 있습니다.

## 설치 준비 점검

"설치할 준비가 됐는지", "사람이 무엇을 해야 하는지"를 묻는 요청에 씁니다. 클러스터를 바꾸지 않습니다. 대상 앱이 지정되지 않으면 [앱 설치 순서](#앱-설치-순서) 표의 순서대로 모든 앱을 봅니다.

앱마다 다음을 실행합니다.

1. [검사] 공통 시작의 context 확인과 사전 검사.
   ```bash
   kubectl --context "<context>" get nodes
   make ops-preflight APP=<app> PROFILE=prod KUBE_CONTEXT="<context>"
   ```
2. [조회] 앱 가이드 `사람이 하는 일` 표의 `완료 확인` 칸에 있는 명령. 명령이 없고 `사용자 보고`라고 적힌 행은 실행하지 않고 "확인 필요"로 둡니다.
3. [조회] 앱 가이드 `한눈에 보기`의 `먼저 필요한 것`에 다른 앱이 있으면 그 앱이 설치됐는지 확인합니다.
   ```bash
   make drift-check APP=<먼저 필요한 앱> KUBE_CONTEXT="<context>" DRIFT_JSON=1 DRIFT_SKIP_MANIFEST=1
   ```
   `findings`에 `배포 기록 없음`이나 `대상 워크로드 없음`이 있으면 아직 설치되지 않은 것입니다.
4. [검사] 이미지를 빌드하는 앱(Airflow·Portal)은 `make build-tools-check`도 실행합니다.

결과는 앱별로 한 표에 모읍니다. 실행하지 않은 확인을 완료로 쓰지 않습니다.

| 열 | 내용 |
| --- | --- |
| 항목 | 가이드의 일 이름 또는 검사 이름 |
| 상태 | `완료` / `미완료` / `확인 필요`(명령으로 확인할 수 없음) |
| 근거 | 실행한 명령과 출력의 핵심 한 줄 |
| 할 사람과 할 일 | `미완료`·`확인 필요`일 때만. 가이드 `사람이 하는 일` 표의 문구와 방법 링크를 그대로 옮김 |

마지막에 "지금 배포할 수 있는 앱"과 "사람 작업이 끝나야 하는 앱"을 나눠 적습니다. 남은 서버 작업은 [pending](shared/docs/infrastructure/pending.md)에 반영합니다.

## 배포 후 공통 마무리

1. [조회] `make ops-deploy`가 출력한 JSON 줄에서 `failedStep`이 `null`이고 `driftResultCode`가 `0`인지 확인합니다. `driftResultCode`가 1·2이면 공통 시작 4번의 명령으로 근거를 조회합니다.
2. [조회] 앱 가이드의 C를 실행합니다.
3. [변경] 운영 기록: 서버에서 확인된 값이 [인프라 정보](shared/docs/infrastructure/README.md)와 다르면 해당 원본을 `서버 조회` 상태로 고치고, 완료된 [pending](shared/docs/infrastructure/pending.md) 행을 삭제합니다. 남은 서버 작업은 행으로 추가합니다. 날짜·완료 기록·비밀값은 쓰지 않습니다.
4. [사람] 로그인·파일 송수신 같은 사용자 기능은 [기능 확인](shared/docs/operations/02-deploy.md#접속기능-검증)의 시나리오로 확인합니다.

보고에는 다음을 담습니다.

- 대상 앱, context, 배포 commit(`git log -1 --oneline`)
- 실행한 단계와 명령, 결과(성공/실패/생략)
- `ops-deploy`의 JSON 요약과 대조 근거, smoke 결과
- 사람이 해야 할 남은 일(클러스터 밖 작업만), 수정한 운영 기록 파일

## 장애 조회

앱이 동작하지 않거나 접속이 안 된다는 요청은 아래 순서로 확인합니다. 모두 [조회]입니다.

1. 어느 앱인지 정합니다. 주소나 namespace로 들어온 요청은 각 앱 가이드의 `한눈에 보기` 표로 앱을 찾습니다. 여러 앱이 함께 안 되면 공용 Traefik(`etch-sso`)과 노드 상태부터 봅니다.
   ```bash
   kubectl --context "<context>" get nodes
   kubectl --context "<context>" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
   ```
2. 앱 하나의 상태를 한 번에 모읍니다. smoke, Pod 상태와 대기 사유, PVC, 최근 Warning 이벤트, 문제가 있는 Pod의 로그 끝을 출력하고 마지막에 볼 곳을 알려 줍니다.
   ```bash
   make ops-diagnose APP=<app> KUBE_CONTEXT="<context>"
   ```
   마지막 줄이 `진단 결과: 정상`이면 서버 쪽 이상이 없는 것이므로 사용자의 접속 경로(DNS·방화벽·브라우저)를 확인하도록 안내합니다. `이상 <n>건`이면 `## 볼 곳`에 나온 아래 표의 행과 앱 가이드의 `문제 해결과 멈춤 조건`을 봅니다. `조회 불가`면 context·kubeconfig 문제입니다.
3. 더 필요하면 개별 명령으로 조회합니다. `<namespace>`는 앱 가이드의 `한눈에 보기` 표에 있습니다.
   ```bash
   kubectl --context "<context>" -n <namespace> describe pod <Pod 이름>
   kubectl --context "<context>" -n <namespace> logs <Pod 이름> --all-containers --tail=100
   kubectl --context "<context>" -n <namespace> logs <Pod 이름> -c <컨테이너> --previous --tail=100
   make <app>-smoke KUBE_CONTEXT="<context>"
   ```
4. 아래 표에서 증상에 맞는 조치를 합니다. 조치가 `없음. 보고`이거나 표에 없는 증상이면 고치려 하지 말고 진단 출력의 해당 부분과 함께 보고합니다.

진단 출력에는 서버명·주소가 그대로 나옵니다. 외부로 전달할 때는 `make ops-diagnose ... | make -s ops-redact`처럼 [서버 상태 보고](shared/docs/operations/04-drift.md#서버-상태-보고)의 별칭 규칙을 거칩니다.

| 증상 | 먼저 볼 것 | 운영 agent가 할 수 있는 조치 |
| --- | --- | --- |
| kubectl timeout / Forbidden | API VIP·인증서·context / 계정 권한 | 없음. 보고 |
| Node NotReady | 런타임·kubelet·CNI·디스크·시간 | 없음. 보고 |
| Pending, PVC Pending | events의 자원·taint·nodeSelector·StorageClass·PV affinity | 없음. 보고 |
| ImagePullBackOff | 이미지 tag·사내 미러·CA·노드의 이미지 접근 | 사내 빌드 이미지면 `make <app>-image` 재실행. 노드의 사내 CA 신뢰·미러 문제면 보고 |
| CrashLoopBackOff | `logs --previous`, 종료 코드, env·DB 연결 | env 오류면 보고. 일시 오류면 `kubectl -n <namespace> rollout restart <워크로드>` 한 번 |
| 404 / 503 | Ingress host·경로·Traefik 감시 namespace / Pod·Service endpoint | 앱의 `make <app>-up` 재실행 |
| TLS 오류 | 공용 TLS 등록 host·SAN·만료·체인. smoke는 시스템 신뢰 목록과 `deploy/shared/certs/ca`의 사내 CA로 검증 | [공용 TLS 등록](#공용-tls-등록) 재실행. 사내 CA 파일이 없으면 배치를 요청 |
| smoke의 `DNS 조회 실패` | DNS 미등록 | `make <app>-smoke KUBE_CONTEXT="<context>" SMOKE_CONNECT=<APP VIP 주소>`로 서비스 자체를 확인하고 DNS 등록을 요청 |
| 로그인 반복·callback 실패 | issuer·redirect URI·client secret·시간·HTTPS 전달 | 없음. 보고 |

Pod·Job 삭제와 Secret 수정으로 직접 고치지 않습니다. 재시작은 위 표의 한 번만 합니다.
클러스터 초기화(`init`·`reset`), PVC 삭제, namespace 재생성은 복구 절차로 쓰지 않습니다.

## 공통 절차와 기록

| 작업 | 문서 |
| --- | --- |
| 클러스터 구축·Worker 가입·API server OIDC | [공통 절차](shared/docs/README.md#클러스터) |
| Traefik·VIP, 인증서 준비·추출·적용 | [공통 절차](shared/docs/README.md#https인증서) |
| 저장소 clone·갱신 | [서버 파일 받기](shared/docs/operations/01-checkout.md) |
| 수동 접속·기능 검증 | [배포 준비와 검증](shared/docs/operations/02-deploy.md) |
| 변경 유형별 반영, Worker 추가, 백업·복구 | [운영](shared/docs/operations/03-operations.md) |
| checkout과 서버 대조, 배포 기록, 서버 상태 보고 | [배포 상태 대조](shared/docs/operations/04-drift.md) |
| env·Secret 작성·검사 | [환경설정](shared/docs/configuration/environment.md) |
| 이 폴더를 수정하는 개발 agent의 규칙 | [배포 지침](AGENTS.md) |
