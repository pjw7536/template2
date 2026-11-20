# Registry 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

사내 이미지 저장소(Zot)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 사내에서 빌드한 이미지(Airflow·Portal)를 보관하고 각 노드가 내려받게 하는 OCI registry |
| namespace | `registry` (Deployment `registry`, Secret `registry-htpasswd`) |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/registry`(없으면 `registry-up`이 UID·GID 1000으로 생성) |
| 주소 | `https://store.etch.samsungds.net`. DNS → APP VIP 443 → 공용 Traefik hostPort 443 → Zot |
| 배포 명령 | `make ops-deploy APP=registry` = 준비 검사 → `registry-check` → `registry-up` → `registry-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, PVC `Bound`, `/v2/`가 200 또는 401 |
| 먼저 필요한 것 | 앱 `ingress`(공용 Traefik), `store.etch.samsungds.net`을 SAN에 가진 인증서 파일 |

## 구성

- push: 관리 호스트의 `make airflow-image`·`make portal-image`가 htpasswd 계정으로 로그인한 뒤 올립니다.
- pull: 각 노드의 containerd가 익명으로 내려받습니다. 외부 공개 이미지는 계속 사내 미러에서 받습니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. 공용 Traefik은 앱 [ingress](../shared/ingress/README.md)가 배포하고, `registry` namespace 감시는 `registry-up`이 추가합니다. 큰 레이어 업로드를 위해 HTTPS entrypoint의 읽기 제한이 600초여야 하며 ingress 원본에 선언돼 있습니다.
- 저장: 지정 Worker 한 대의 local PV(`Retain`)입니다. Pod가 멈추면 이미지를 아직 받지 않은 노드에서 새 Pod가 시작되지 않고, 이미 받은 이미지로 실행 중인 Pod는 영향이 없습니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 앱 `ingress`(공용 Traefik) 배포([ingress 가이드](../shared/ingress/README.md)) | `make ops-preflight APP=registry KUBE_CONTEXT="<context>"`의 `먼저 필요한 앱 ingress`가 `[통과]` |
| `store.etch.samsungds.net`이 SAN에 있는 `fullchain.crt`·`private.key`를 `deploy/shared/certs/etch.samsungds.net/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급)). 공용 TLS 등록은 `ops-deploy`의 준비 검사가 자동으로 수행 | `make ops-preflight APP=registry KUBE_CONTEXT="<context>"`의 `공용 TLS store.etch.samsungds.net`이 `[통과]` 또는 `[자동 준비]` |
| Worker(`NODE_NAME`)의 `DATA_HOST_PATH` 상위 경로가 데이터 디스크에 마운트되고 `STORAGE_SIZE` 이상 여유. 최초 설치면 `DATA_HOST_PATH` 폴더가 없거나 비어 있음 | `df -hT /appdata`와 `sudo -n ls -A /appdata/registry`(Worker가 관리 호스트와 같은 서버일 때. 다른 노드면 [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'df -hT /appdata; sudo -n ls -A /appdata/registry'`) |
| DNS `store.etch.samsungds.net` → APP VIP 등록([DNS](../shared/docs/infrastructure/access.md#dns)) | `getent hosts store.etch.samsungds.net` |
| 관리 호스트와 이미지를 받을 모든 노드가 인증서의 발급 CA를 신뢰. 저장소 주소로 확인하므로 최초 설치에서는 C에서 확인 | [노드와 관리 호스트의 CA 신뢰](docs/01-operations.md#노드와-관리-호스트의-ca-신뢰) |

DNS가 아직 없어도 배포와 smoke는 진행합니다. smoke가 APP VIP로 서비스를 확인해 `DNS 미등록`으로 표시합니다. 이미지 push와 노드의 pull은 이름이 조회되어야 하므로 C의 push·pull 확인 전에 DNS를 등록합니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `REGISTRY_ENV` | Registry env 경로 | `deploy/registry/env/k8s.env` |
| `REGISTRY_PUSH_ENV` | push 계정 파일. Secret `registry-htpasswd`가 없을 때만 사용하고 기존 Secret은 바꾸지 않음 | `deploy/registry/env/push-initial.env` |

다른 값을 쓰면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 경로를 모든 명령에 같게 붙입니다.

env 파일의 키입니다.

| 키 | 의미 |
| --- | --- |
| `NODE_NAME` | registry를 실행할 Worker의 `kubernetes.io/hostname` 값 |
| `REGISTRY_IMAGE` | 사내 ghcr.io 미러의 Zot 고정 tag 이미지 |
| `PREPARE_IMAGE` | 저장 폴더 준비 Job이 쓰는 셸 포함 이미지(Docker Hub 사내 미러의 busybox 고정 tag) |
| `IMAGE_PULL_SECRET` | Zot 이미지를 받을 때 필요한 pull Secret 이름. 인증이 없으면 비움 |
| `REGISTRY_HOST` | 노드와 관리 호스트가 접근할 DNS 이름. scheme·포트 없이 입력 |
| `DATA_HOST_PATH` | Worker의 이미지 저장 폴더 |
| `STORAGE_SIZE` | PV/PVC 용량. 디스크 여유에 맞춰 지정 |

push 계정 파일의 키는 `REGISTRY_USER`, `REGISTRY_PASSWORD` 두 개입니다.

## A. 최초 설치

1. [검사] 준비 검사로 먼저 필요한 앱 `ingress`와 입력을 확인합니다.
   ```bash
   make ops-preflight APP=registry KUBE_CONTEXT="<context>"
   ```
   성공: `[배포 차단]`으로 시작하는 줄이 없습니다. `[자동 준비]` 줄(공용 TLS 등록)은 2번에서 자동으로 실행됩니다.
   - `[배포 차단] 먼저 필요한 앱 ingress`: [ingress 가이드](../shared/ingress/README.md)의 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`를 먼저 실행하고 이 검사를 다시 실행합니다.
   - `[배포 차단] 공용 TLS store.etch.samsungds.net`: 인증서 파일이 없는 것입니다. [사전 준비](#사전-준비)의 둘째 행을 수행합니다.
   - 그 밖의 `[배포 차단]`: 그 줄의 `볼 곳`에 적힌 [접근 경로](../shared/docs/infrastructure/access.md) 절로 해결합니다.
2. [변경] 배포. 준비 검사(공용 TLS 자동 등록) 뒤 namespace·push 계정 Secret·저장 폴더·PV·Zot·Ingress를 한 번에 준비하고 smoke와 대조를 수행합니다.
   ```bash
   make ops-deploy APP=registry KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 단계별 출력은 `registry 입력·노드·저장소·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` → `registry 배포 완료: https://store.etch.samsungds.net/v2/` → `smoke 통과: registry` 순서입니다.
   push 계정 Secret은 bcrypt htpasswd로 만듭니다. `htpasswd`(apache2-utils)가 없으면 Python `crypt`를 쓰고, 둘 다 쓸 수 없으면 오류로 끝납니다([문제 해결](#문제-해결과-멈춤-조건)).
   - `failedStep`이 `preflight`면 JSON의 `blocked`를 1번과 같은 방법으로 해결하고 같은 명령을 다시 실행합니다.
   - `pending`에 `DNS store.etch.samsungds.net`이 있으면 배포는 끝난 것입니다. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지 태그 | [변경] `make ops-deploy APP=registry KUBE_CONTEXT="<context>"`. `registry-up`은 매번 registry를 다시 시작함 |
| 공용 Traefik 설정 변경(읽기 제한 등) | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`([ingress 가이드](../shared/ingress/README.md#b-업데이트)) 뒤 C의 읽기 제한 조회 |
| 인증서 갱신 | [변경] 새 파일을 `deploy/shared/certs/etch.samsungds.net/`에 둔 뒤 [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=store.etch.samsungds.net`으로 실행. 성공: `공용 TLS 등록 완료: store.etch.samsungds.net` |
| push 계정 교체 | [승인] 이전 계정으로는 push할 수 없게 되고 registry가 한 번 다시 시작합니다. 새 계정 이름을 보여 주고 승인받은 뒤 [계정 교체](docs/01-operations.md#push-계정-교체)의 `make registry-account-rotate`. 배포 기록도 이 명령이 함께 갱신 |
| 이미지 태그 삭제 | [승인] 되돌릴 수 없습니다. 사용 중인 이미지와 대상 태그를 대조해 보여 주고 승인받은 뒤 [삭제](docs/01-operations.md#이미지-삭제와-용량-정리) |
| 주소 전환(`registry.etch.samsungds.net`) | [승인] 공개 주소가 바뀝니다. 이 주소를 쓰는 앱과 영향을 보여 주고 승인받은 뒤 [주소 전환](docs/01-operations.md#registry-주소로-전환) |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n registry get pods,pvc,ingress
make registry-smoke KUBE_CONTEXT="<context>"
kubectl --context "<context>" -n etch-sso get deployment traefik -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}' | grep -Fc -- '--entrypoints.websecure.transport.respondingTimeouts.readTimeout=600s'
```

성공: Pod Running, PVC Bound, `smoke 통과: registry`(`/v2/` 200 또는 401), 마지막 줄 `1`(HTTPS entrypoint의 읽기 제한 600초 적용). 마지막 줄이 `0`이면 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`로 ingress 원본을 다시 적용하고(Traefik이 다시 시작됩니다) 다시 조회합니다.
smoke 뒤에 `(DNS 미등록 host 1개)`가 붙으면 서비스는 정상이고 DNS 등록만 남은 것이므로 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.

최초 설치와 새 Worker를 받았을 때는 이어서 push·pull을 확인합니다. 새 Worker는 그 노드에서 1·3번만 실행합니다.

1. [조회] 관리 호스트와 이미지를 받을 노드마다 [HTTPS 신뢰를 확인](docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)합니다. 신뢰 오류가 나면 같은 절의 CA 등록을 수행합니다.
2. [변경] 관리 호스트에서 [시험 이미지를 push](docs/01-operations.md#수동-pushpull-시험)합니다.
3. [변경] 이미지를 받을 노드마다 [시험 이미지를 pull](docs/01-operations.md#수동-pushpull-시험)합니다.

노드 명령은 관리 호스트에서 [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--command`로 전달합니다. 명령을 실행하지 못한 노드는 확인하지 못한 것으로 보고에 남기고 나머지 노드를 계속 확인합니다.

## 문제 해결과 멈춤 조건

smoke는 DNS에 없는 host를 APP VIP로 다시 확인합니다. `DNS 미등록. APP VIP 직접 접속: …`이면 서비스는 정상이고 smoke도 통과하며, 남은 일은 [DNS](../shared/docs/infrastructure/access.md#dns) 절의 등록입니다. 도구의 오류는 `registry 실행 실패: <원인>`으로 출력되고, 모든 앱에 공통인 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

| 증상 | 원인과 조치 |
| --- | --- |
| smoke `정상 응답 없음: /v2/ 404` | registry Ingress와 Traefik의 `registry` namespace 감시. [변경] `make registry-up KUBE_CONTEXT="<context>"` 재실행 |
| smoke `DNS 조회 실패, APP VIP 직접 접속도 실패: …` | DNS와 무관하게 서비스에 닿지 않음. 아래 `연결 실패`·`TLS 검증 실패` 행 중 뒤에 붙은 원인에 맞는 행을 따름 |
| smoke `연결 실패` | APP VIP 443 전달 또는 Traefik hostPort 443. [조회] `make ingress-smoke KUBE_CONTEXT="<context>"`로 Traefik Pod와 노드 443을 확인하고, 정상이면 [APP VIP와 LB](../shared/docs/infrastructure/access.md#app-vip와-lb) 절로 VIP 전달을 확인 |
| smoke `TLS 검증 실패` | 공용 TLS 등록·SAN·체인. [변경] [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=store.etch.samsungds.net`으로 다시 실행. 같은 오류면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 SAN·체인이 맞는 인증서를 준비 |
| `공용 TLS 마운트가 없습니다`, `deployments.apps "traefik" not found` | 공용 Traefik이 없거나 이전 정의. [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` 뒤 같은 명령 재실행 |
| `store.etch.samsungds.net: 공용 TLS 인증서가 없습니다` | 인증서가 등록되지 않음. 파일이 있으면 [변경] `make ops-deploy APP=registry KUBE_CONTEXT="<context>"`의 준비 검사가 등록. 파일이 없으면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 준비 |
| `registry 대상 노드의 hostname·Ready·스케줄 가능 상태를 확인하세요`, `registry 대상 Worker의 차단 taint를 확인하세요` | [조회] `kubectl --context "<context>" get node <NODE_NAME 값>`으로 상태를 확인하고 [장애 조회](../README.md#장애-조회)의 Node NotReady 행을 따름 |
| `bcrypt htpasswd를 만들 수 없습니다` | 관리 호스트에 `htpasswd`가 없고 Python `crypt`도 쓸 수 없음. [변경] [관리 호스트 sudo](../shared/docs/infrastructure/access.md#관리-호스트-sudo)로 `sudo -n apt-get install -y apache2-utils`를 실행하고 `command -v htpasswd`로 확인한 뒤 같은 명령 재실행 |
| `push 계정 파일의 REGISTRY_USER·REGISTRY_PASSWORD를 확인하세요` | 계정 파일의 값이 비었거나 자리표시자. 실제 값이 든 계정 파일을 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)로 준비해 `REGISTRY_PUSH_ENV=<경로>`로 지정 |
| Pod 재시작 반복 | 저장 폴더 권한(1000:1000). [조회] `kubectl --context "<context>" -n registry logs deployment/registry --tail=100`과 [저장 폴더 확인](docs/01-operations.md#저장-폴더-직접-준비) |
| Zot 이미지 pull 실패(`ErrImagePull`, `ImagePullBackOff`) | [장애 조회](../README.md#장애-조회)의 ImagePullBackOff 행. 사내 미러에 `REGISTRY_IMAGE`가 없으면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입) 절 |
| push 중 `x509` / `401` / timeout | CA 신뢰([확인과 등록](docs/01-operations.md#노드와-관리-호스트의-ca-신뢰)) / 로그인에 쓴 계정 파일과 Secret `registry-htpasswd`의 계정 / C의 읽기 제한 조회와 VIP 경로 |
| 노드에서 `curl`은 성공하고 `crictl pull`만 `x509` | containerd가 CA 등록 전의 신뢰 목록을 사용. [승인] [containerd 재시작](docs/01-operations.md#노드와-관리-호스트의-ca-신뢰) |

다음이면 멈추고 보고합니다.

- `기존 registry PV가 Released·Failed 또는 삭제 중입니다`, `기존 registry PV가 다른 PVC에 예약되어 있습니다`, `기존 PV 경로·노드와 DATA_HOST_PATH·NODE_NAME이 다릅니다`. 기존 이미지 데이터가 있습니다. PV·PVC를 지우거나 다시 만들지 않고 `claimRef`를 고치지 않습니다.
- PVC가 `Pending`으로 남음. PV·PVC를 지우거나 다시 만들지 않습니다.
- 기존 `/appdata/registry`에 내용이 있는데 PV `registry-data`가 없음(사전 준비의 `ls -A`에 파일이 보이고 검사가 `신규 정적 PV·저장 폴더 생성 예정`을 출력). 이전 설치의 이미지 데이터일 수 있습니다. 폴더의 내용을 지우거나 소유자를 바꾸지 않고 그 위에 새로 설치하지 않습니다.
- 데이터를 다른 Worker로 옮겨야 함. Worker의 데이터 폴더를 옮기거나 지우지 않습니다. 데이터 경로 이전은 [승인] 변경이며 [Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)의 순서를 따릅니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [운영 작업](docs/01-operations.md) | 노드와 관리 호스트의 CA 신뢰, 수동 push·pull 시험, 이미지 push 규칙, 삭제와 용량 정리, push 계정 교체, 저장 폴더 직접 준비, 주소 전환 |
