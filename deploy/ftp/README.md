# 00. FTP 시작 안내

이 폴더는 Kubernetes Worker에서 파일을 받는 FTP 서버의 설치·운영을 관리합니다.
FTP 라벨이 붙은 Linux 노드마다 Pod가 하나씩 실행됩니다. 업로드한 파일은 접속한 노드에 저장됩니다.

## 지금 필요한 작업

| 현재 상태 | 다음 작업 | 문서 |
| --- | --- | --- |
| FTP 서버가 없음 | 노드·디스크·계정 준비 → 검사 → 배포 | [01. 서버 설치](01_SERVER_SETUP.md) |
| 사내 Worker별 IP:6380으로 수신 | 각 Worker 준비 → CP1에서 사내 이미지 overlay 일괄 적용 | [01. 대상·노드 준비](01_SERVER_SETUP.md#2-클러스터와-worker-선택) → [03. 사내 배포](03_KUBERNETES.md#사내-이미지로-각-worker에-배포) |
| 서버가 실행 중 | 접속·저장 확인, 노드 추가·중단, 문제 해결 | [02. 운영](02_OPERATIONS.md) |
| 이미지·저장 경로 변경 또는 수동 배포 필요 | Kubernetes 원본과 overlay 확인 | [03. 원본과 수동 배포](03_KUBERNETES.md) |

## 어디에 뜨고 어디에 저장되나요?

```text
관리 PC / 클러스터 관리 서버
  └─ make ftp-up: 지정한 Worker에 FTP 라벨을 붙이고 DaemonSet 배포
       ├─ Worker A: FTP Pod 1개 ← 클라이언트가 A의 IP:6380으로 접속
       │    └─ A의 /appdata/data_movement/파일
       └─ Worker B: FTP Pod 1개 ← 클라이언트가 B의 IP:6380으로 접속
            └─ B의 /appdata/data_movement/파일
```

라벨은 `etch.io/ftp-enabled=true`입니다. 모든 노드에 자동으로 설치하지 않습니다.
배포 명령을 실행하는 컴퓨터와 FTP가 실행되는 Worker는 달라도 됩니다.

노드 간 파일은 자동 복제·이동되지 않으며 소비 앱이 다른 노드에 있으면 별도 전송 또는 공유 저장소가 필요합니다.
`/appdata/data_movement`가 없는 Worker에서는 Pod 시작 전에 폴더를 자동 생성합니다. 기존 데이터는 유지하며 하위 파일의 소유권은 자동 변경하지 않습니다.
컨테이너 내부 경로는 `/data/data_movement`, 외부 PC의 kind 매핑도 기존 경로를 유지합니다.
기존 Worker의 `/data/data_movement` 파일은 자동으로 옮겨지지 않습니다. 재배포 전에
[Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)에 따라 복사·검증합니다.

## 실행 명령

저장소 루트에서 실행합니다. 실제 입력 준비는 [서버 설치](01_SERVER_SETUP.md)를 따릅니다.

| 명령 | 하는 일 |
| --- | --- |
| `make server-check APP=ftp PROFILE=prod` | 원본 셸 문법·Kustomize 렌더 검사 |
| `make ftp-check` | 명시한 context의 대상 노드·계정·원본 검사. 클러스터 변경 없음 |
| `make ftp-up` | 같은 검사 후 namespace·Secret·라벨·DaemonSet 적용, 기동 대기 |
| `make ftp-test` | 배포 스크립트 회귀 검사. 클러스터 불필요 |

`ftp-check`와 `ftp-up`에는 `KUBE_CONTEXT`, `FTP_NODES`, `FTP_CREDENTIAL_FILE`이 필요합니다.
계정 파일은 서버에서 [credentials.env.example](credentials.env.example)의 `FTP_USER`, `FTP_PASS`를 입력해 사용합니다.
권한 `600` 적용과 절대 경로 지정은 [계정 파일 준비](01_SERVER_SETUP.md#4-관리-호스트의-계정-파일-준비)를 따릅니다.
모든 대상 노드는 같은 계정을 사용합니다. 기존 Secret이 있으면 입력 계정과 비교하고, 다르면 중단합니다.
`ftp-up`은 기본 원본을 적용합니다. 사내 이미지 overlay를 사용할 때는 위 사내 배포 절차로 같은 overlay를 적용합니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
