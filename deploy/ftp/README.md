# FTP 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

선택한 노드에서 파일을 직접 주고받는 FTP를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 선택한 Linux 노드마다 FTP Pod 하나를 실행해 클라이언트가 그 노드로 파일을 올리고 받게 함 |
| namespace | `etch-ftp` (DaemonSet `ftp`, 노드 라벨 `etch.io/ftp-enabled=true`) |
| 실행 노드 | 지정한 노드마다 1개. 파일은 각 노드의 `/appdata/data_movement`(노드 간 복제 없음) |
| 접속 | 각 노드 주소의 TCP 6380, passive 8076–8079. Service·Ingress·VIP 없음 |
| 배포 명령 | `make ops-deploy APP=ftp` = `ftp-check` → `ftp-up` → `ftp-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, 대상 노드마다 Pod 1개 Ready |
| 먼저 필요한 것 | 최초 설치의 대상 노드 목록, 방화벽 |

## 구성

- 배치: `etch.io/ftp-enabled=true` 라벨이 있는 Linux 노드마다 `hostNetwork` Pod 하나를 실행합니다. 라벨은 `ftp-up`이 `FTP_NODES`의 노드에 붙입니다. control plane은 env의 `FTP_ALLOW_CONTROL_PLANE`이 `true`(기본값)이고 `FTP_NODES`에 이름을 넣었을 때만 대상이 됩니다.
- 접속: 클라이언트가 각 노드 InternalIP의 TCP 6380과 passive 포트 8076–8079로 직접 접속합니다. IPv4 직접 접속과 passive 모드용이며 TLS나 NAT 주소를 자동 설정하지 않습니다.
- 저장: 접속한 노드의 `/appdata/data_movement`(hostPath)에만 저장하고 노드 사이에 복제하지 않습니다. 폴더가 없으면 Pod 배포 시 생성됩니다. 로그인 후 업로드 폴더는 `data_movement/`입니다.
- 계정: 모든 대상 노드가 Secret `ftp-credentials`를 공유합니다. `ftp-up`은 Secret이 없을 때만 계정 파일로 만들고 기존 Secret은 바꾸지 않습니다.
- 의존: Portal·Keycloak·공용 Traefik 없이 설치할 수 있습니다. namespace 정책이 `hostNetwork`·`hostPath`를 허용해야 하고, 노드가 [env/prod.env](env/prod.env)의 `FTP_IMAGE`(사내 미러)를 받을 수 있어야 합니다.

대상 노드·접속 주소·검증 결과는 [FTP 서비스 기록](../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신), 방화벽은 [FTP 네트워크 기록](../shared/docs/infrastructure/network.md#ftp-직접-접속)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 방법으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 최초 설치의 대상 노드 결정([기준](docs/01-install.md#2-클러스터와-대상-노드-선택)) | 사용자가 `FTP_NODES` 값을 전달. 갱신은 필요 없음 |
| 각 대상 노드의 저장 디스크·기존 파일·포트 점유 확인([방법](docs/01-install.md#3-각-노드의-저장-폴더와-포트-확인)) | 사용자 보고 |
| 방화벽 개방: 허용 출발지 → 각 노드 TCP 6380, 8076–8079 | `make ftp-smoke KUBE_CONTEXT="<context>"`의 tcp 줄은 관리 호스트에서의 연결만 확인. 사용자 PC 접속은 사용자 보고 |
| 선택: PC에서 passive 전송 시험([방법](docs/02-operations.md#2-업로드다운로드-확인)) | 사용자 보고 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `FTP_NODES` | 쉼표로 구분한 전체 노드 이름(공백·중복 없음) | 비우면 이미 FTP 라벨이 있는 노드를 그대로 사용. 최초 설치는 사용자에게 받음 |
| `FTP_CREDENTIAL_FILE` | 계정 파일 경로 | `deploy/ftp/env/initial-account.env`. 기존 Secret과 다르면 검사가 멈춤 |
| `FTP_ENV` | FTP env 경로 | `deploy/ftp/env/prod.env` |

env 파일의 키입니다. 형식과 제약은 [배포 env와 도구 동작](docs/01-install.md#배포-env와-도구-동작)에 있습니다.

| 키 | 의미 |
| --- | --- |
| `FTP_IMAGE` | 사내 Docker Hub 미러의 FTP 이미지. 고정 tag 또는 sha256 digest 포함 |
| `IMAGE_PULL_SECRET` | 이미지를 받을 때 필요한 pull Secret 이름. 인증이 없으면 비움 |
| `FTP_ALLOW_CONTROL_PLANE` | `FTP_NODES`에 넣은 control plane의 허용 여부. 생략하면 `true` |

계정 파일의 키는 `FTP_USER`, `FTP_PASS`입니다. 파일 권한이 넓으면 도구가 소유자 전용(0600)으로 좁힙니다. 형식은 [계정 파일 준비](docs/01-install.md#4-관리-호스트의-계정-파일-준비)에 있습니다.

## A. 최초 설치

1. [사람] 대상 노드 목록을 받습니다. [조회] 받은 이름이 클러스터에 있는지 확인합니다.
   ```bash
   kubectl --context "<context>" get nodes
   ```
2. [변경] 배포. 노드 라벨·계정 Secret·DaemonSet을 적용합니다.
   ```bash
   make ops-deploy APP=ftp KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2>
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지 | [변경] `make ops-deploy APP=ftp KUBE_CONTEXT="<context>"` (`FTP_NODES` 생략) |
| 노드 추가 | 새 노드의 방화벽을 [사람]에게 확인한 뒤 `FTP_NODES`에 기존 노드와 새 노드를 모두 넣어 A-2. [준비 사항](docs/02-operations.md#3-노드-추가재배포) |
| 노드에서 FTP 중단, 계정 변경 | 멈추고 사람에게 묻기(접속 중단·모든 클라이언트 영향). 방법: [노드 중단](docs/02-operations.md#4-특정-노드에서-중단), [계정 변경](docs/02-operations.md#5-계정-변경) |
| 별도 overlay 운영 중 | `make ftp-up`을 쓰지 않음. 사람에게 overlay 경로를 받은 뒤 [변경] [방법](docs/01-install.md#별도-overlay-배포)의 절차로 적용 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true
kubectl --context "<context>" -n etch-ftp get daemonset ftp
make ftp-smoke KUBE_CONTEXT="<context>"
```

성공: DaemonSet DESIRED·CURRENT·READY가 대상 노드 수와 같음, `smoke 통과: ftp`.

smoke는 관리 호스트에서 각 FTP 노드의 6380 연결만 확인합니다. passive 포트와 로그인·업로드·다운로드는 [클라이언트 전송 시험](docs/02-operations.md#2-업로드다운로드-확인)으로 확인합니다.

## 문제 해결과 멈춤 조건

실패하면 [장애 조회](../README.md#장애-조회)의 명령을 namespace `etch-ftp`로 실행합니다. Pod·접속 증상별 확인 항목은 [문제 해결](docs/02-operations.md#6-문제-해결)에 있습니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `ftp-check`의 `FTP 라벨이 있는 노드가 없습니다` | 최초 설치입니다. A-1로 대상 노드를 받아 `FTP_NODES`를 지정 |
| 배포 중 실패 | 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 다시 실행. 재실행은 파일 데이터를 삭제하지 않음 |
| smoke tcp 줄이 `연결 실패` | Pod 상태를 조회하고, Pod가 Ready이면 관리 호스트 → 노드 6380 경로 확인을 요청 |

멈추고 사람에게 묻는 조건입니다.

- `ftp-check`에서 Secret 불일치(기존 계정 파일과 다름), 노드 상태 오류, control plane 선택 거부, `기존 FTP 노드도 FTP_NODES에 포함하세요`
- 노드 포트 점유, `ImagePullBackOff`, FailedMount
- `kubectl apply -k deploy/ftp/k8s` 직접 적용이 필요해 보이는 경우. 실행하지 않습니다(env가 반영되지 않음).

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비와 별도 overlay 배포](docs/01-install.md) | 대상 노드 선택 기준, 각 노드의 저장 폴더·포트 확인, 방화벽 요청, 계정 파일 형식, env 키와 도구 동작, 별도 overlay 배포 |
| [접속 확인과 운영](docs/02-operations.md) | Pod 위치 확인, 클라이언트 전송 시험, 노드 추가·중단, 계정 변경, 문제 해결, 실행 계약과 원본 파일 |
