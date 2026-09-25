# 00. FTP 시작 안내

이 폴더는 Kubernetes Worker에서 파일을 받는 FTP 서버의 설치·운영을 관리합니다.
**FTP 라벨이 붙은 Linux 노드마다 Pod가 하나씩 실행되고, 업로드한 파일은 접속한 노드에 저장됩니다.**

## 지금 필요한 작업

| 현재 상태 | 다음 작업 | 문서 |
| --- | --- | --- |
| FTP 서버가 없음 | 노드·디스크·계정 준비 → 검사 → 배포 | [01. 서버 설치](01_SERVER_SETUP.md) |
| 서버가 실행 중 | 접속·저장 확인, 노드 추가·중단, 문제 해결 | [02. 운영](02_OPERATIONS.md) |
| 이미지·저장 경로 변경 또는 수동 배포 필요 | Kubernetes 원본과 overlay 확인 | [03. 원본과 수동 배포](03_KUBERNETES.md) |

## 어디에 뜨고 어디에 저장되나요?

```text
관리 PC / 클러스터 관리 서버
  └─ make ftp-up: 지정한 Worker에 FTP 라벨을 붙이고 DaemonSet 배포
       ├─ Worker A: FTP Pod 1개 ← 클라이언트가 A의 IP:6380으로 접속
       │    └─ A의 /data/data_movement/파일
       └─ Worker B: FTP Pod 1개 ← 클라이언트가 B의 IP:6380으로 접속
            └─ B의 /data/data_movement/파일
```

라벨은 `etch.io/ftp-enabled=true`입니다. 모든 노드에 자동으로 설치하지 않습니다.
배포 명령을 실행하는 컴퓨터와 FTP가 실행되는 Worker는 달라도 됩니다.
노드 간 파일은 자동 복제·이동되지 않으며 소비 앱이 다른 노드에 있으면 별도 전송 또는 공유 저장소가 필요합니다.

## 실행 명령

저장소 루트에서 실행합니다. 실제 입력 준비는 [서버 설치](01_SERVER_SETUP.md)를 따릅니다.

| 명령 | 하는 일 |
| --- | --- |
| `make server-check APP=ftp PROFILE=prod` | 원본 셸 문법·Kustomize 렌더 검사 |
| `make ftp-check` | 명시한 context의 대상 노드·계정·원본 검사. 클러스터 변경 없음 |
| `make ftp-up` | 같은 검사 후 namespace·Secret·라벨·DaemonSet 적용, 기동 대기 |
| `make ftp-test` | 배포 스크립트 회귀 검사. 클러스터 불필요 |

`ftp-check`와 `ftp-up`에는 `KUBE_CONTEXT`, `FTP_NODES`, `FTP_CREDENTIAL_FILE`이 필요합니다.
기존 Secret은 보존하며 입력 계정이 다르면 중단합니다. 모든 대상 노드는 같은 계정을 사용합니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
