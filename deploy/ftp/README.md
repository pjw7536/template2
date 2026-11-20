# FTP 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

선택한 노드에서 파일을 직접 주고받는 FTP를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 선택한 Linux 노드마다 FTP Pod 하나를 실행해 클라이언트가 그 노드로 파일을 올리고 받게 함 |
| namespace | `etch-ftp` (DaemonSet `ftp`, 노드 라벨 `etch.io/ftp-enabled=true`) |
| 실행 노드 | 지정한 노드마다 1개. 파일은 각 노드의 `/appdata/data_movement`(노드 간 복제 없음) |
| 접속 | 각 노드 주소의 TCP 6380, passive 8076–8079. Service·Ingress·VIP 없음 |
| 배포 명령 | `make ops-deploy APP=ftp` = 준비 검사 → `ftp-check` → `ftp-up` → `ftp-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 대상 노드마다 Pod 1개 Ready |
| 먼저 필요한 것 | 최초 설치의 대상 노드 목록, 방화벽 |

## 구성

- 배치: `etch.io/ftp-enabled=true` 라벨이 있는 Linux 노드마다 `hostNetwork` Pod 하나를 실행합니다. 라벨은 `ftp-up`이 `FTP_NODES`의 노드에 붙입니다. control plane은 env의 `FTP_ALLOW_CONTROL_PLANE`이 `true`(기본값)이고 `FTP_NODES`에 이름을 넣었을 때만 대상이 됩니다.
- 접속: 클라이언트가 각 노드 InternalIP의 TCP 6380과 passive 포트 8076–8079로 직접 접속합니다. IPv4 직접 접속과 passive 모드용이며 TLS나 NAT 주소를 자동 설정하지 않습니다.
- 저장: 접속한 노드의 `/appdata/data_movement`(hostPath)에만 저장하고 노드 사이에 복제하지 않습니다. 폴더가 없으면 Pod 배포 시 생성됩니다. 로그인 후 업로드 폴더는 `data_movement/`입니다.
- 계정: 모든 대상 노드가 Secret `ftp-credentials`를 공유합니다. `ftp-up`은 Secret이 없을 때만 계정 파일로 만들고 기존 Secret은 바꾸지 않습니다.
- 의존: Portal·Keycloak·공용 Traefik 없이 설치할 수 있습니다. namespace 정책이 `hostNetwork`·`hostPath`를 허용해야 하고, 노드가 [env/prod.env](env/prod.env)의 `FTP_IMAGE`(사내 미러)를 받을 수 있어야 합니다.

대상 노드·접속 주소·검증 결과는 [FTP 서비스 기록](../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신), 방화벽은 [FTP 네트워크 기록](../shared/docs/infrastructure/network.md#ftp-직접-접속)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 최초 설치의 대상 노드 목록(`FTP_NODES`). 요청에 주어지는 입력입니다([선택 기준](docs/01-install.md#2-클러스터와-대상-노드-선택)) | `kubectl --context "<context>" get nodes`의 `NAME`에 요청받은 노드 이름이 모두 있음. 업데이트는 `kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true`가 기존 대상 노드를 출력 |
| 각 대상 노드의 저장 디스크·기존 파일·포트 사용 확인 | [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)으로 [저장 폴더와 포트 확인](docs/01-install.md#3-각-노드의-저장-폴더와-포트-확인)의 명령을 실행. 포트 조회가 `포트 사용 없음`을 출력 |
| 방화벽 개방: 허용 출발지 → 각 노드 TCP 6380, 8076–8079([대상](../shared/docs/infrastructure/network.md#ftp-직접-접속)) | [방화벽](../shared/docs/infrastructure/access.md#방화벽) |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `FTP_ENV` | FTP env 경로 | `deploy/ftp/env/prod.env`. 저장소 밖 env를 쓰면 모든 명령에 같은 값을 붙임([운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)) |
| `FTP_NODES` | 쉼표로 구분한 전체 노드 이름(공백·중복 없음) | 비우면 이미 FTP 라벨이 있는 노드를 그대로 사용. 최초 설치에는 필수이며 요청에 주어지는 입력 |
| `FTP_CREDENTIAL_FILE` | 계정 파일 경로 | `deploy/ftp/env/initial-account.env`. 기존 Secret과 다르면 검사가 멈춤 |

env 파일의 키입니다. 형식과 제약은 [배포 env와 도구 동작](docs/01-install.md#배포-env와-도구-동작)에 있습니다.

| 키 | 의미 |
| --- | --- |
| `FTP_IMAGE` | 사내 Docker Hub 미러의 FTP 이미지. 고정 tag 또는 sha256 digest 포함 |
| `IMAGE_PULL_SECRET` | 이미지를 받을 때 필요한 pull Secret 이름. 인증이 없으면 비움 |
| `FTP_ALLOW_CONTROL_PLANE` | `FTP_NODES`에 넣은 control plane의 허용 여부. 생략하면 `true` |

계정 파일의 키는 `FTP_USER`, `FTP_PASS`입니다. 파일 권한이 넓으면 도구가 소유자 전용(0600)으로 좁힙니다. 형식은 [계정 파일 준비](docs/01-install.md#4-관리-호스트의-계정-파일-준비)에 있습니다.

## A. 최초 설치

1. [조회] 후보 노드를 조회해 요청의 대상 노드 이름이 `NAME`에 모두 있는지 확인합니다.
   ```bash
   kubectl --context "<context>" get nodes
   ```
   요청에 대상 노드가 없으면 조회한 `NAME` 목록을 제시하고 FTP를 실행할 노드 이름 목록만 요청합니다. 대상을 임의로 고르지 않습니다.
2. [변경] 배포. 노드 라벨·계정 Secret·DaemonSet을 적용합니다. `FTP_NODES`에는 1단계에서 확인한 노드 이름을 쉼표로 이어 넣습니다.
   ```bash
   make ops-deploy APP=ftp KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2>
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `FTP 배포 완료`가 있습니다.
   실패하면 JSON의 `failedStep`과 `오류:` 줄을 [문제 해결과 멈춤 조건](#문제-해결과-멈춤-조건)의 표에서 찾아 조치한 뒤 같은 명령을 다시 실행합니다. `failedStep`이 `preflight`이고 `blocked`의 `item`이 `앱 검사`면 `ftp-check`가 실패한 것입니다. `make ftp-check KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2>`를 직접 실행해 `오류:` 줄을 확인합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

다른 env·계정 파일로 설치했으면 아래 명령에 같은 `FTP_ENV=<경로>`·`FTP_CREDENTIAL_FILE=<경로>`를 붙입니다. `make ops-deploy`의 성공 기준은 A-2와 같고, 실행 뒤 [C. 배포 후 확인](#c-배포-후-확인)을 수행합니다.

| 변경 | 실행 |
| --- | --- |
| env·이미지 | [변경] `make ops-deploy APP=ftp KUBE_CONTEXT="<context>"` (`FTP_NODES` 생략) |
| 노드 추가 | [변경] 새 노드의 [준비 사항](docs/02-operations.md#3-노드-추가재배포)을 확인한 뒤 `make ops-deploy APP=ftp KUBE_CONTEXT="<context>" FTP_NODES=<기존 노드와 새 노드 전체>` |
| 노드에서 FTP 중단 | [승인] 그 노드의 접속이 끊깁니다. [노드 중단](docs/02-operations.md#4-특정-노드에서-중단) |
| 계정 변경 | [승인] 계정 Secret을 교체하고 모든 노드의 Pod를 다시 시작합니다. [계정 변경](docs/02-operations.md#5-계정-변경) |
| 별도 overlay로 설치한 서버 | [변경] [별도 overlay 절차](docs/01-install.md#별도-overlay-배포)로 적용하고 기록. overlay 경로는 [운영 위치](../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)에서 찾음 |

## C. 배포 후 확인

1. [조회] 대상 노드, DaemonSet, 관리 호스트에서 각 노드 6380까지의 연결을 확인합니다.
   ```bash
   kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true
   kubectl --context "<context>" -n etch-ftp get daemonset ftp
   make ftp-smoke KUBE_CONTEXT="<context>"
   ```
   성공: DaemonSet DESIRED·CURRENT·READY가 대상 노드 수와 같음, 마지막 줄이 `smoke 통과: ftp`.
2. [변경] 대상 노드마다 [업로드·다운로드 확인](docs/02-operations.md#2-업로드다운로드-확인)을 수행합니다. smoke는 6380 연결만 확인하므로 passive 포트와 로그인·업로드·다운로드는 이 시험으로 확인합니다.

## 문제 해결과 멈춤 조건

실패하면 [장애 조회](../README.md#장애-조회)의 명령을 namespace `etch-ftp`로 실행합니다. Pod·접속 증상별 확인 항목은 [문제 해결](docs/02-operations.md#6-문제-해결)에 있습니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `FTP 라벨이 있는 노드가 없습니다` | 최초 설치인데 `FTP_NODES`가 없음. A-1로 대상 노드를 확인해 `FTP_NODES`를 붙여 다시 실행 |
| `존재하지 않는 노드: <이름>` | `FTP_NODES`의 이름이 `kubectl --context "<context>" get nodes`의 `NAME`과 다름. 이름을 고쳐 다시 실행 |
| `FTP_NODES는 공백·중복 없이 쉼표로 구분한 노드 이름 목록이어야 합니다.` | 값의 공백·중복을 없애고 다시 실행 |
| `기존 FTP 노드도 FTP_NODES에 포함하세요: <노드>` | 이미 FTP 라벨이 있는 노드가 목록에서 빠짐. 표시된 노드를 `FTP_NODES`에 더해 다시 실행. 노드를 빼려는 것이면 B의 `노드에서 FTP 중단` |
| `Control plane 배포에는 FTP_ALLOW_CONTROL_PLANE=true가 필요합니다: <노드>` | 사용 중인 env가 control plane을 막음. 그 노드를 `FTP_NODES`에서 빼거나 [control plane 설정](docs/01-install.md#control-plane도-대상에-추가하기)을 따름 |
| `FTP_IMAGE에는 고정 tag 또는 sha256 digest가 포함된 이미지 주소를 지정하세요.` 등 env 오류 | env의 키와 형식을 [배포 env와 도구 동작](docs/01-install.md#배포-env와-도구-동작)과 대조. 다른 값이 필요하면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 사본을 `FTP_ENV=<경로>`로 지정 |
| `기존 FTP Secret과 계정 파일이 다릅니다` | 설치에 쓴 계정 파일이 지금 지정한 파일과 다름. 설치에 쓴 계정 파일을 `FTP_CREDENTIAL_FILE=<경로>`로 지정해 다시 실행. 저장소 밖 파일의 위치는 [운영 위치](../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)에서 찾음 |
| 배포 중 실패 | 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 다시 실행. 재실행은 파일 데이터를 삭제하지 않음 |
| smoke tcp 줄이 `연결 실패` | [조회] `kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide`로 Pod 상태를 확인. Pod가 Ready이면 관리 호스트에서 그 노드 6380까지의 경로를 [방화벽](../shared/docs/infrastructure/access.md#방화벽) 절로 확인 |
| `ImagePullBackOff`, FailedMount, Pod 시작 실패 | [문제 해결](docs/02-operations.md#6-문제-해결)의 같은 증상 행 |

다음이면 멈추고 보고합니다.

- 설치에 쓴 계정 파일을 찾지 못해 `기존 FTP Secret과 계정 파일이 다릅니다`를 해결할 수 없는 경우. Secret `ftp-credentials`를 지우거나 덮어쓰지 않습니다. 계정을 바꾸는 요청일 때만 B의 `계정 변경`을 따릅니다.
- `Ready·cordon·taint 상태를 확인하세요: <노드>`가 나온 경우. 노드를 uncordon하거나 taint·역할 라벨을 제거하지 않습니다. `kubectl --context "<context>" describe node <노드>`의 조건과 taint를 보고합니다.
- 대상 노드의 6380·8076–8079를 다른 프로세스가 쓰고 있는 경우. 그 프로세스를 중지하지 않습니다.
- 대상 노드의 이전 경로 `/data/data_movement`에 파일이 남아 있는 경우. 그대로 배포하지 않습니다. 배포하면 새 빈 폴더를 쓰게 되므로 [Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)이 먼저이며 데이터 경로 이전은 [승인]입니다.
- `kubectl apply -k deploy/ftp/k8s`를 직접 실행해야 할 것처럼 보이는 경우. 실행하지 않습니다. env가 반영되지 않아 공개 이미지를 사용합니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비와 별도 overlay 배포](docs/01-install.md) | 대상 노드 선택 기준, 각 노드의 저장 폴더·포트 확인 명령, 방화벽 대상, 계정 파일 형식, env 키와 도구 동작, 별도 overlay 배포와 기록 |
| [접속 확인과 운영](docs/02-operations.md) | Pod 위치 확인, 업로드·다운로드 확인, 노드 추가·중단, 계정 변경, 문제 해결, 실행 계약과 원본 파일 |
