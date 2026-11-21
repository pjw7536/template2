# 서버 배포

사내 Kubernetes 클러스터에 앱을 설치·운영하는 안내입니다. 사람과 사내 운영 agent(opencode `ops`)가 같은 문서를 봅니다.
명령은 관리 호스트의 저장소 전체 checkout 루트에서 실행합니다. 서버·주소·적용 상태의 원본은 [사내 인프라 정보](shared/docs/infrastructure/README.md)입니다.

- [문서 읽는 법](#문서-읽는-법)
- [실행 규칙](#실행-규칙)
- [앱 설치 순서](#앱-설치-순서)
- [모든 작업 공통 시작](#모든-작업-공통-시작)
- [공용 TLS 등록](#공용-tls-등록) · [사내 CA 묶음](#사내-ca-묶음) · [공용 Traefik 검사·갱신](#공용-traefik-검사갱신) · [이미지 빌드 도구](#이미지-빌드-도구) · [이미지 빌드와 발행](#이미지-빌드와-발행)
- [설치 준비 점검](#설치-준비-점검)
- [배포 후 공통 마무리](#배포-후-공통-마무리)
- [장애 조회](#장애-조회)
- [공통 절차와 기록](#공통-절차와-기록)

## 문서 읽는 법

| 문서 | 내용 |
| --- | --- |
| 이 문서 | 모든 앱에 공통인 규칙과 절차 |
| 앱 가이드 | 앱마다 하나이며 [앱 설치 순서](#앱-설치-순서) 표에 링크가 있습니다. 모든 앱이 같은 순서의 절을 가집니다: `한눈에 보기` → `구성` → `사전 준비` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `문제 해결과 멈춤 조건` → `상세 문서` |
| `deploy/<app>/docs/` | 가이드에 없는 상세: 입력 키 설명, 사전 준비, 백업·교체·이전 같은 운영 작업 |
| [공통 절차](shared/docs/README.md) | 클러스터 구축, Traefik·VIP, 인증서, checkout, 배포 상태 대조 |
| [사내 인프라 정보](shared/docs/infrastructure/README.md) | 서버·주소·저장소·운영 위치, [접근 경로](shared/docs/infrastructure/access.md), [서버 적용 대기 작업](shared/docs/infrastructure/pending.md), 외부 전달용 [별칭 표](shared/docs/infrastructure/aliases.json) |
| [전환 런북](shared/docs/operations/05-transition.md) | 이미 배포된 서버에 새 checkout을 적용할 때 한 번 수행하는 순서 |

### 단계 표시

모든 실행 단계에는 영향과 승인 필요 여부를 표시합니다. 운영 agent가 준비부터 배포 후 검증까지 진행합니다.

| 표시 | 뜻 | 운영 agent의 행동 |
| --- | --- | --- |
| [조회] | 클러스터·파일을 읽기만 함 | 바로 실행 |
| [검사] | 입력·원본을 검사하고 클러스터를 바꾸지 않음 | 바로 실행. 실패하면 오류 문구의 조치를 따름 |
| [변경] | 클러스터·서버를 바꿈 | 바로 실행. 실행한 명령과 결과를 보고에 남김 |
| [승인] | 되돌릴 수 없거나 사용 중인 서비스가 중단되는 변경 | 검사와 준비를 마친 뒤 명령·대상·영향을 보여 주고 사용자 승인 후 실행. 같은 대상과 영향에 대해 이미 승인받았으면 그 승인을 사용 |

[승인]으로 표시하는 변경은 다음뿐입니다. 그 밖의 변경은 [변경]입니다.

- 데이터를 되돌릴 수 없는 변경: 이미 운영 중인 DB의 schema migration, 이미지 태그·계정·Secret의 삭제나 교체, 데이터 경로 이전
- 사용 중인 서비스가 끊기는 변경: 노드·kubelet·containerd·API server의 재시작, 공용 Traefik의 backend 변경, 공개 주소 변경
- 최초 설치는 끊길 서비스가 없으므로 [변경]입니다. `make ops-deploy`의 재배포로 앱 Pod가 다시 시작되는 것도 [변경]입니다. 재시작으로 실행 중 작업이 끊길 수 있는 앱은 앱 가이드의 `B. 업데이트`가 실행 전에 확인할 것을 적습니다.

표시가 적용되는 범위는 다음과 같습니다.

- 단계 번호 뒤나 명령 블록 바로 앞 문장의 표시는 그 단계의 명령 전체에 적용됩니다.
- `모두 [조회]입니다`라고 쓴 절은 그 절의 모든 명령이 [조회]입니다.
- 앱 가이드 `사전 준비` 표의 `완료 확인` 칸은 [조회]입니다. 완료 여부를 확인하고, 미완료면 같은 행의 `준비 작업`을 수행합니다.
- 앱 가이드 `B. 업데이트` 표의 실행 칸은 적힌 표시를 따릅니다.
- **표시가 없는 명령 블록은 실행하지 않습니다.** 개념 설명이나 형식 예시입니다. 필요한 절차인데 표시가 없으면 문서 오류이므로 그 위치를 보고합니다.

명령의 `<...>`는 실제 값으로 바꿉니다.

| 자리표시 | 값을 찾는 곳 |
| --- | --- |
| `<context>` | 사용자가 지정한 값, 없으면 [운영 위치](shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)의 서버 기본 context. `kubectl config get-contexts`에 있는 이름이어야 함 |
| `<app>` | [apps.json](shared/apps.json)의 앱 이름 하나 |
| `<namespace>` | 앱 가이드의 `한눈에 보기` 표 |
| `<APP VIP 주소>` | [별칭 표](shared/docs/infrastructure/aliases.json)의 `VIP-APP` |
| `<노드>` | `kubectl --context "<context>" get nodes`의 `NAME` |

## 실행 규칙

1. 기본 실행 위치는 관리 호스트의 저장소 루트입니다. 다른 노드나 외부 시스템(DNS·방화벽·LB·인증서 발급·AD FS·외부 DB)에서 하는 단계는 [접근 경로](shared/docs/infrastructure/access.md)의 해당 절에 적힌 방법으로 수행합니다.
2. Kubernetes 명령에는 `KUBE_CONTEXT="<context>"` 또는 `--context "<context>"`를 붙입니다. `kubectl config use-context`를 쓰지 않습니다.
3. 명령마다 새 셸이 열릴 수 있으므로 `export`한 변수에 의존하지 말고 값을 명령에 직접 씁니다. 저장소 밖 env를 쓰면 그 경로를 앱의 env 변수(예: `AIRFLOW_ENV=<경로>`)로 검사·배포·대조·진단의 각 명령에 같게 붙입니다. 변수 이름은 앱 가이드의 `입력` 표에 있습니다.
4. 처음 설치와 업데이트 모두 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`가 기본입니다. 다음을 순서대로 수행합니다.
   - 준비 검사: 접속, 저장소 원본, 먼저 필요한 앱, 입력 파일, chart, 사내 CA 묶음, 빌드 도구, 공개 host의 공용 TLS와 DNS를 확인합니다. chart 받기·CA 묶음 만들기·빌드 도구 설치·공용 TLS 등록은 필요한 파일이 있으면 자동으로 실행합니다.
   - 배포 단계: [apps.json](shared/apps.json)의 `steps`. 검사(`<app>-check`)가 클러스터를 바꾸는 단계보다 먼저입니다.
   - [배포 상태 대조](shared/docs/operations/04-drift.md)
   - 한 번에 앱 하나만 받습니다. `APP`을 빼면 실행되지 않습니다. 앱 가이드가 요구하는 추가 입력(예: `FTP_NODES=...`)은 같은 명령 뒤에 붙이면 모든 단계에 전달됩니다.
   - 다시 실행해도 됩니다. 이미 있는 리소스와 이미 올린 이미지는 건너뛰지만, `<app>-up`은 Pod를 다시 시작할 수 있습니다.
5. `ops-deploy`의 결과는 마지막에 출력되는 `{"app":`으로 시작하는 JSON 한 줄입니다.

   | 필드 | 뜻 | 할 일 |
   | --- | --- | --- |
   | `failedStep` | `null`이면 모든 단계 성공. `preflight`면 준비 검사에서 막힘. 그 밖에는 실패한 단계 이름 | `null`이 아니면 6번 |
   | `driftResultCode` | `0` 일치 또는 설정 전용 앱의 대조 생략, `1` 불일치·경고, `2` 판정 불가 | `0`이 아니면 `make drift-check APP=<app> KUBE_CONTEXT="<context>"`로 근거 조회. 설정 전용 앱은 해당 가이드의 검증 출력 확인 |
   | `blocked` | 저장소 도구로 해결하지 못한 준비 항목. `item`·`detail`과, 있으면 `command`·`reference` | `reference`가 가리키는 [접근 경로](shared/docs/infrastructure/access.md) 절로 해결한 뒤 같은 명령을 다시 실행 |
   | `pending` | 배포는 끝났지만 남은 일(DNS 등록 등) | `reference`의 절로 수행하고, 못 하면 [pending](shared/docs/infrastructure/pending.md)에 기록 |

   `failedStep`이 `null`이고 `driftResultCode`가 `0`이면 성공입니다.
6. 단계가 실패하면 앱 가이드의 `문제 해결과 멈춤 조건`에서 같은 오류를 찾습니다. 조치가 적혀 있으면 한 번 수행하고 같은 명령을 다시 실행합니다. 다시 실패하거나 멈춤 조건에 해당하거나 가이드에 없는 오류면 그 앱만 멈추고 실패한 명령·종료 코드·오류 마지막 20줄을 보고합니다.
7. [변경]·[승인] 단계를 실행한 뒤에는 그 단계에 적힌 성공 문구나 바로 뒤의 확인 명령으로 결과를 확인하고, 확인한 출력의 핵심 줄을 보고에 남깁니다. 성공 문구가 적혀 있지 않으면 `make <app>-smoke`와 [조회] 명령으로 확인합니다. 확인하지 못한 변경을 완료로 보고하지 않습니다.
8. 여러 앱을 요청받으면 [앱 설치 순서](#앱-설치-순서) 표의 순서대로 앱마다 공통 시작부터 마무리까지 반복합니다. 한 앱이 멈추면 그 앱을 먼저 필요로 하는 앱만 건너뛰고 나머지를 계속한 뒤 앱별 결과를 함께 보고합니다.
9. 비밀번호·토큰·개인키 값을 응답·운영 기록·보고서에 옮겨 적지 않습니다. env 파일과 Secret은 진단에 필요하면 읽을 수 있습니다.
10. 사내망 밖으로 전달하는 내용에는 서버 IP·서버명·사내 도메인을 쓰지 않습니다. [서버 상태 보고](shared/docs/operations/04-drift.md#서버-상태-보고)의 `make ops-report` 출력만 전달합니다.
11. 사용자에게 요청하는 것은 [접근 경로](shared/docs/infrastructure/access.md)의 사용 규칙을 따릅니다. 먼저 그 절의 방법과 `찾는 방법`으로 직접 진행하고, 접근·권한·입력이 실제로 막혔을 때만 그 절의 `막히면 요청할 것`을 요청합니다. 요청할 때는 막힌 단계, 시도한 명령과 결과, 필요한 것을 함께 알립니다. 그 단계에 의존하지 않는 작업은 계속합니다.

### 하지 않는 일

- PV·PVC·namespace·CRD·DB·Worker 데이터 폴더를 삭제·이동하지 않습니다. `helm uninstall`, `kubectl delete namespace`, `kubectl drain`을 실행하지 않습니다.
- `kubectl apply -k deploy/shared/ingress`를 직접 실행하지 않습니다. 공용 Traefik의 감시 namespace와 VIP 배치가 기본값으로 돌아갑니다. `make ops-deploy APP=ingress`를 씁니다.
- `make k8s-env APP=keycloak ...`을 실행하지 않습니다. 기존 Keycloak Secret을 덮어씁니다.
- Portal overlay를 `kubectl apply -k`로 직접 적용하지 않습니다. 이미지 tag가 `auto`로 남습니다.
- 운영 agent는 저장소 파일(코드·manifest·env·스크립트·문서)을 수정하지 않습니다. 예외는 `deploy/shared/docs/infrastructure/`의 운영 기록뿐이며, 검사를 통과시키려고 파일을 고치지 않습니다. 다른 입력값이 필요하면 [운영 입력 파일](shared/docs/infrastructure/access.md#운영-입력-파일)을 씁니다.
- 대화형 명령(`vi`, 입력을 기다리는 `read`, 비밀번호 프롬프트)을 실행하지 않습니다. 파일은 비대화형으로 쓰고 비밀값은 파일로 전달합니다.

## 앱 설치 순서

앱 간 의존 관계의 원본은 [apps.json](shared/apps.json)의 `dependsOn`입니다. 준비 검사가 먼저 필요한 앱의 배포 여부를 확인합니다.

| 순서 | 앱 | 먼저 필요한 것 |
| --- | --- | --- |
| 1 | [공용 Traefik(ingress)](shared/ingress/README.md) | Ready Worker |
| 2 | [Keycloak](keycloak/README.md) | ingress, 공용 TLS |
| 3 | [MinIO](minio/README.md), [Registry](registry/README.md) | ingress, 공용 TLS |
| 4 | [Airflow](airflow/README.md) | ingress, Keycloak, Registry, 공용 TLS, 빌드 도구 |
| 4 | [Monitoring](monitoring/README.md) | ingress, 공용 TLS |
| 4 | [Headlamp](headlamp/README.md) | ingress, Keycloak, 제어면 API server OIDC |
| 4 | [FTP](ftp/README.md) | 대상 노드·방화벽 |
| 5 | [Portal](portal/README.md) | ingress, Keycloak, MinIO, Registry, 외부 PostgreSQL, 빌드 도구 |
| 6 | [권한관리(IAM)](iam/README.md) | Keycloak |

클러스터와 관리 호스트가 아직 없다면 [공통 절차](shared/docs/README.md)의 클러스터 구축과 [관리 호스트 준비](shared/docs/operations/04-drift.md#관리-호스트-준비)를 먼저 합니다.

## 모든 작업 공통 시작

1. [변경] checkout 갱신. `git pull`이 실패하면 현재 checkout으로 진행하고 실패를 보고에 남깁니다.
   ```bash
   git pull --ff-only
   git status --short
   git log -1 --oneline
   ```
   대상 배포 경로(`deploy/<app>`)나 소스(`apps/<app>`)에 미커밋 변경이 있으면 그 앱은 멈추고 보고합니다.
   갱신으로 commit이 바뀌었으면 [전환 런북](shared/docs/operations/05-transition.md)의 `적용 여부 확인`을 먼저 실행합니다.
2. [조회] context와 노드를 확인합니다. 선택한 context 이름이 목록에 없거나 노드 조회가 실패하면 [Kubernetes API](shared/docs/infrastructure/access.md#kubernetes-api) 절로 확인합니다.
   ```bash
   kubectl config get-contexts
   kubectl --context "<context>" get nodes
   ```
3. [조회] 현재 상태를 대조합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```
   JSON의 `resultCode`와 `apps[].findings`를 읽습니다. 0은 일치, 1은 불일치·경고, 2는 판정 불가입니다. `배포 기록 없음`이고 `대상 워크로드 없음`이면 앱 가이드의 A(최초 설치), 그 밖에는 B(업데이트)입니다. 유효한 JSON이 없으면 2번의 접속 문제입니다.

준비 상태만 묻는 요청은 [설치 준비 점검](#설치-준비-점검)을 사용합니다.

## 공용 TLS 등록

공개 host의 인증서를 공용 Traefik에 등록합니다. `make ops-deploy`의 준비 검사가 host마다 등록 여부를 확인하고, `deploy/shared/certs/<사이트>/`에 그 host를 SAN에 가진 `fullchain.crt`·`private.key`가 있으면 자동으로 등록합니다. 인증서를 갱신했거나 한 host만 다시 등록할 때 아래 명령을 직접 씁니다.

[변경] host마다 한 번씩 등록합니다. SAN 인증서 하나를 여러 host가 함께 써도 host마다 반복합니다. 이미 같은 인증서가 등록돼 있으면 변경 없이 끝납니다.

```bash
make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=<공개 host> TLS_CERT_FILE="$PWD/deploy/shared/certs/<사이트>/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/<사이트>/private.key"
```

성공: `공용 TLS 등록 완료: <host>`.
실패: 준비 검사가 `[배포 차단] 공용 TLS <host>`를 내거나 이 명령이 `인증서와 공개 도메인이 다릅니다`로 끝나면 그 host를 SAN에 가진 인증서 파일이 없는 것입니다. [인증서 발급](shared/docs/infrastructure/access.md#인증서-발급) 절로 파일을 준비합니다. 추출과 검증은 [인증서 추출](shared/docs/certificates/extract.md), 등록 뒤 확인은 [인증서 적용](shared/docs/certificates/apply.md)에 있습니다.

## 사내 CA 묶음

Keycloak OIDC를 검증하는 앱(Airflow·Headlamp), 관리 API 도구, smoke가 사용합니다. `deploy/shared/certs/ca/`에 사내 Root·Issuing CA 파일이 있으면 준비 검사가 자동으로 만듭니다. CA를 교체했을 때 아래 명령으로 다시 만듭니다.

[변경]
```bash
make ca-bundle CA_HOST=sso.etch.samsungds.net
```

성공: `CA 묶음 준비 완료: deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`. `CA 인증서가 없습니다`면 [인증서 발급](shared/docs/infrastructure/access.md#인증서-발급) 절로 CA 파일을 준비합니다.
이 명령은 묶음을 CA 폴더의 현재 내용으로 다시 만듭니다. CA를 교체했으면 다시 실행한 뒤 묶음을 쓰는 앱(Airflow의 OIDC CA ConfigMap, Headlamp의 `headlamp-oidc-setup`)을 갱신합니다.

## 공용 Traefik 검사·갱신

공용 Traefik은 앱 `ingress`입니다. 설치·갱신·확인은 [ingress 가이드](shared/ingress/README.md)를 따릅니다.

[변경] 배치(VIP backend)를 바꾸지 않는 설치·갱신입니다. 감시 namespace와 현재 배치를 보존합니다.

```bash
make ops-deploy APP=ingress KUBE_CONTEXT="<context>"
```

성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.

[승인] backend 노드 추가·변경(`VIP_BACKENDS` 지정)은 서비스 진입 경로를 바꿉니다. 값과 영향을 보여 주고 승인받은 뒤 [backend 확장](shared/docs/ingress/expand.md)을 따릅니다. 기존 backend를 빼지 않습니다.

## 이미지 빌드 도구

Airflow·Portal 이미지는 이 checkout에서 빌드해 사내 이미지 저장소로 push합니다. `make ops-deploy`가 검사 다음 단계(`<app>-image`)로 수행하며 nerdctl·BuildKit이 필요합니다. 준비 검사가 도구를 확인하고 없으면 설치합니다. 직접 확인·설치할 때 아래를 씁니다.

1. [검사]
   ```bash
   make build-tools-check
   ```
   성공: `빌드 도구 준비 완료`.
2. [변경] 도구가 없다고 나오면 설치합니다. 비밀번호 없는 sudo가 필요하고 containerd는 재시작하지 않습니다.
   ```bash
   make build-tools-install
   ```
   성공: `빌드 도구 준비 완료`. sudo가 거부되면 [관리 호스트 sudo](shared/docs/infrastructure/access.md#관리-호스트-sudo), 다운로드가 실패하면 [파일 반입](shared/docs/infrastructure/access.md#파일-반입) 절로 진행합니다.

이미지 tag는 소스 내용으로 자동으로 정해지고, registry에 같은 tag가 있으면 빌드하지 않습니다. 저장소 파일의 tag를 고칠 필요가 없습니다.
push에는 [Registry](registry/README.md)가 먼저 배포돼 있어야 하고, 관리 호스트가 저장소 주소의 인증서를 신뢰해야 합니다. 설치 내용은 [빌드 도구 준비](airflow/docs/02-artifacts.md#containerd-빌드-도구-준비)에 있습니다.

## 이미지 빌드와 발행

이미지 발행만 요청받았을 때 씁니다. [변경] 대상 앱에 해당하는 명령을 하나 실행합니다.

```bash
make <app>-image KUBE_CONTEXT="<context>"
```

`<app>`은 `portal` 또는 `airflow`입니다. push 계정 파일을 별도로 두었으면 같은 명령에 `REGISTRY_PUSH_ENV=<경로>`를 지정합니다. 성공은 이미지별 `push 완료` 또는 `registry에 이미 있는 tag라 빌드하지 않았습니다` 출력으로 확인합니다. 앱 배포는 별도로 요청받았을 때 실행합니다.

## 설치 준비 점검

"설치할 준비가 됐는지", "무엇이 더 필요한지"를 묻는 요청에 씁니다. 클러스터를 바꾸지 않습니다. 대상 앱이 지정되지 않으면 [앱 설치 순서](#앱-설치-순서) 표의 순서대로 모든 앱을 봅니다.

앱마다 다음을 실행합니다.

1. [검사] 준비 검사. 접속, 저장소 원본, 먼저 필요한 앱, 입력 파일, chart, CA 묶음, 빌드 도구, 공용 TLS, DNS, 앱 자체 검사를 한 번에 확인합니다.
   ```bash
   make ops-preflight APP=<app> KUBE_CONTEXT="<context>"
   ```
   줄마다 `[통과]`, `[자동 준비]`(배포할 때 표시한 명령이 자동 실행됨), `[배포 차단]`(`볼 곳`의 접근 경로 절로 해결), `[안내]`(배포를 막지 않는 남은 일) 중 하나로 시작합니다. 마지막 줄은 `준비 검사 결과: 배포 가능` 또는 `준비 검사 결과: 남은 항목 <n>건`입니다.
2. [조회] 앱 가이드 `사전 준비` 표에서 준비 검사가 다루지 않는 행(노드의 CA 신뢰, 제어면 설정, 방화벽, 외부 계정 등)을 `완료 확인` 칸의 방법으로 확인합니다. 접근이 막혀 확인하지 못하면 시도한 명령과 결과를 근거에 적고 `확인 필요`로 둡니다.

결과는 앱별로 한 표에 모읍니다. 실행하지 않은 확인을 완료로 쓰지 않습니다.

| 열 | 내용 |
| --- | --- |
| 항목 | 준비 검사의 항목 이름 또는 가이드의 준비 작업 이름 |
| 상태 | `완료` / `미완료` / `확인 필요`(접근이 막혀 확인하지 못함) |
| 근거 | 실행한 명령과 출력의 핵심 한 줄 |
| 다음 조치 | `미완료`·`확인 필요`일 때만. 실행할 명령 또는 접근 경로 절과 막힌 경우 요청할 것 |

마지막에 앱별 배포 가능 여부와 막힌 단계를 적습니다. 남은 서버 작업은 [pending](shared/docs/infrastructure/pending.md)에 반영합니다.

## 배포 후 공통 마무리

1. [조회] `make ops-deploy`가 출력한 JSON 줄에서 `failedStep`이 `null`이고 `driftResultCode`가 `0`인지 확인합니다. `driftResultCode`가 1·2이면 `make drift-check APP=<app> KUBE_CONTEXT="<context>"`로 근거를 조회합니다.
2. [조회] 앱 가이드의 C를 실행합니다. smoke가 확인하지 않는 기능은 [화면 기능 확인](shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 [기능 검증](shared/docs/operations/02-deploy.md#접속기능-검증) 시나리오를 확인합니다.
3. [변경] JSON의 `pending`에 있는 남은 일(DNS 등록 등)을 `reference`의 접근 경로 절로 수행합니다. 수행하지 못한 일은 [pending](shared/docs/infrastructure/pending.md)에 행으로 남깁니다.
4. [변경] 운영 기록: 서버에서 확인된 값이 [인프라 정보](shared/docs/infrastructure/README.md)와 다르면 해당 원본을 `서버 조회` 상태로 고치고, 완료된 pending 행을 삭제합니다. 처음 사용한 접근 방법은 [접근 경로](shared/docs/infrastructure/access.md)에 기록합니다. 날짜·완료 기록·비밀값은 쓰지 않습니다.

보고에는 다음을 담습니다.

- 대상 앱, context, 배포 commit(`git log -1 --oneline`)
- 실행한 단계와 명령, 결과(성공/실패/생략)
- `ops-deploy`의 JSON 요약과 대조 근거, smoke 결과
- 막힌 단계와 시도한 명령, 요청하는 것, 수정한 운영 기록 파일

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
   마지막 줄이 `진단 결과: 정상`이면 서버 쪽 이상이 없는 것입니다. 사용자의 접속 경로(DNS·방화벽·브라우저)가 원인일 수 있으므로 [DNS](shared/docs/infrastructure/access.md#dns)와 [방화벽](shared/docs/infrastructure/access.md#방화벽) 절의 `찾는 방법`으로 확인하고 결과를 알립니다. `이상 <n>건`이면 `## 볼 곳`에 나온 아래 표의 행과 앱 가이드의 `문제 해결과 멈춤 조건`을 봅니다. `조회 불가`면 [Kubernetes API](shared/docs/infrastructure/access.md#kubernetes-api) 절로 확인합니다.
3. 더 필요하면 개별 명령으로 조회합니다. `<namespace>`는 앱 가이드의 `한눈에 보기` 표에 있습니다.
   ```bash
   kubectl --context "<context>" -n <namespace> describe pod <Pod 이름>
   kubectl --context "<context>" -n <namespace> logs <Pod 이름> --all-containers --tail=100
   kubectl --context "<context>" -n <namespace> logs <Pod 이름> -c <컨테이너> --previous --tail=100
   make <app>-smoke KUBE_CONTEXT="<context>"
   ```
4. 아래 표에서 증상에 맞는 조치를 합니다. 조치가 `보고`이거나 표에 없는 증상이면 고치려 하지 말고 진단 출력의 해당 부분과 함께 보고합니다.

진단 출력에는 서버명·주소가 그대로 나옵니다. 외부로 전달할 때는 `make ops-diagnose ... | make -s ops-redact KUBE_CONTEXT="<context>"`처럼 [서버 상태 보고](shared/docs/operations/04-drift.md#서버-상태-보고)의 별칭 규칙을 거칩니다.

| 증상 | 먼저 볼 것 | 조치 |
| --- | --- | --- |
| kubectl timeout / Forbidden | API VIP·인증서·context / 계정 권한 | [Kubernetes API](shared/docs/infrastructure/access.md#kubernetes-api) 절로 확인. 해결되지 않으면 보고 |
| Node NotReady | 런타임·kubelet·CNI·디스크·시간 | [노드 명령 실행](shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'df -hT; systemctl status kubelet containerd'`로 디스크와 서비스 상태를 [조회]. kubelet이 멈춘 노드에는 명령을 실행할 Job이 뜨지 않으므로, `노드 명령 실패`나 시간 초과면 노드 이름과 `kubectl --context "<context>" describe node <노드>`의 `Conditions`를 보고합니다. 재시작은 [승인] |
| Pending, PVC Pending | events의 자원·taint·nodeSelector·StorageClass·PV affinity | 보고. PV·PVC를 지우거나 다시 만들지 않음 |
| ImagePullBackOff | 이미지 tag·사내 미러·CA·노드의 이미지 접근 | [변경] 사내 빌드 이미지가 저장소에 없으면 `make <app>-image KUBE_CONTEXT="<context>"`. 노드가 저장소 인증서를 신뢰하지 않으면 [노드의 CA 신뢰](registry/docs/01-operations.md#노드와-관리-호스트의-ca-신뢰) |
| CrashLoopBackOff | `logs --previous`, 종료 코드, env·DB 연결 | env 오류면 보고. 일시 오류면 [변경] `kubectl --context "<context>" -n <namespace> rollout restart <워크로드>` 한 번 |
| 404 / 503 | Ingress host·경로·Traefik 감시 namespace / Pod·Service endpoint | 앱 가이드 `문제 해결과 멈춤 조건`의 같은 증상 행의 조치 |
| TLS 오류 | 공용 TLS 등록 host·SAN·만료·체인. smoke는 시스템 신뢰 목록과 `deploy/shared/certs/ca`의 사내 CA로 검증 | [변경] [공용 TLS 등록](#공용-tls-등록)의 명령으로 다시 등록 |
| smoke의 `DNS 조회 실패` | DNS에 없고 APP VIP 직접 접속도 실패 | Traefik과 앱 Ingress를 조회한 뒤 앱 가이드의 404 / 503 조치. DNS만 없으면 smoke가 `DNS 미등록`으로 통과시키며 [DNS](shared/docs/infrastructure/access.md#dns) 절로 등록 |
| 로그인 반복·callback 실패 | issuer·redirect URI·client secret·시간·HTTPS 전달 | 앱 가이드의 같은 증상 행. 없으면 보고 |

Pod·Job 삭제와 Secret 수정으로 직접 고치지 않습니다. 재시작은 위 표의 한 번만 합니다.
클러스터 초기화(`init`·`reset`), PVC 삭제, namespace 재생성은 복구 절차로 쓰지 않습니다.

## 공통 절차와 기록

| 작업 | 문서 |
| --- | --- |
| 클러스터 구축·Worker 가입·API server OIDC | [공통 절차](shared/docs/README.md#클러스터) |
| Traefik·VIP, 인증서 준비·추출·적용 | [공통 절차](shared/docs/README.md#https인증서) |
| 저장소 clone·갱신 | [서버 파일 받기](shared/docs/operations/01-checkout.md) |
| 접속·기능 검증 | [배포 준비와 검증](shared/docs/operations/02-deploy.md) |
| 변경 유형별 반영, Worker 추가, 백업·복구 | [운영](shared/docs/operations/03-operations.md) |
| checkout과 서버 대조, 배포 기록, 서버 상태 보고 | [배포 상태 대조](shared/docs/operations/04-drift.md) |
| 이미 배포된 서버에 새 구조 적용 | [전환 런북](shared/docs/operations/05-transition.md) |
| env·Secret 작성·검사 | [환경설정](shared/docs/configuration/environment.md) |
| 클러스터 밖 작업의 접근 방법 | [접근 경로](shared/docs/infrastructure/access.md) |
| 이 폴더를 수정하는 개발 agent의 규칙 | [배포 지침](AGENTS.md) |
