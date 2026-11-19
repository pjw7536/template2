# FTP 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `etch-ftp` (DaemonSet `ftp`, 노드 라벨 `etch.io/ftp-enabled=true`) |
| 실행 노드 | 사용자가 정한 노드마다 1개. 파일은 각 노드의 `/appdata/data_movement`(노드 간 복제 없음) |
| 접속 | 각 노드 InternalIP의 TCP 6380, passive 8076–8079. Service·Ingress·VIP 없음 |
| 배포 명령 | `make ftp-check` → `make ftp-up` (성공 시 배포 기록 자동) |
| 완료 기준 | 선택한 노드마다 Pod 1개 Ready, 사람이 각 노드 IP로 passive 로그인·업로드·다운로드 확인 |
| 먼저 필요한 것 | 대상 노드 목록, 계정 파일, 방화벽 |

## 사람이 해야 하는 일

- [사람] 대상 노드 결정. `FTP_NODES`는 이미 FTP가 있는 노드까지 포함한 전체 목록
- [사람] 각 노드에서 디스크·포트 확인(3. 각 노드의 저장 폴더와 포트 확인 (사람용 `deploy/ftp/docs/01-install.md#3-각-노드의-저장-폴더와-포트-확인`))
- [사람] 방화벽 개방: 허용 출발지 → 각 노드 TCP 6380, 8076–8079
- [사람] 신규 계정 파일에 `chmod 600 deploy/ftp/env/initial-account.env` 적용. 기존 FTP는 사용 중인 계정 파일 사용
- [사람] PC에서 전송 시험

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `FTP_NODES` | 쉼표로 구분한 전체 노드 이름(공백·중복 없음) | 없음. 사용자에게 받음 |
| `FTP_CREDENTIAL_FILE` | 계정 파일 절대 경로 | 신규는 `$PWD/deploy/ftp/env/initial-account.env`, 기존은 운영 파일 |
| `FTP_ENV` | FTP env 경로 | `deploy/ftp/env/prod.env` |

## A. 최초 설치

1. [사람] 노드 목록·계정 파일 경로·노드 확인·방화벽 요청이 끝났는지 사용자에게 확인하고 실제 `FTP_NODES`를 받습니다. 기존 FTP만 아래 기본 계정 파일을 운영 파일 경로로 바꿉니다.
2. [조회] 노드와 기존 FTP 노드 확인
   ```bash
   kubectl --context "<context>" get nodes -o wide
   kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true -o wide
   ```
   이미 라벨이 있는 노드가 `FTP_NODES`에 모두 포함됐는지 확인합니다.
3. [검사] 원본·입력 검사
   ```bash
   make ftp-check KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2> FTP_CREDENTIAL_FILE="$PWD/deploy/ftp/env/initial-account.env"
   ```
   성공: `입력·노드·기존 Secret·원본 렌더 검사 통과`. 출력된 context·노드·IP가 사용자가 의도한 값인지 보여 주고 확인받습니다.
4. [변경] 배포(승인 필요). namespace·Secret을 없을 때만 만들고 노드에 라벨을 붙인 뒤 적용합니다.
   ```bash
   make ftp-up KUBE_CONTEXT="<context>" FTP_NODES=<노드1,노드2> FTP_CREDENTIAL_FILE="$PWD/deploy/ftp/env/initial-account.env"
   ```
   성공: 노드별 Pod 위치 출력, `FTP 배포 완료`, `배포 기록 저장: etch-ftp/deploy-record-ftp`.
5. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
6. [사람] PC에서 각 노드 IP로 passive 전송 시험을 요청합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지·노드 추가 | 새 노드는 [사람] 확인·방화벽 먼저 → A-3 → A-4 → C. `FTP_NODES`에는 기존 노드도 모두 포함 |
| 노드에서 FTP 중단 | 멈추고 사람에게 묻기(라벨 제거, 해당 노드 접속 중단) |
| 계정 변경 | 멈추고 사람에게 묻기(모든 노드·클라이언트 영향) |
| 별도 overlay 운영 중 | 멈추고 사람에게 묻기. overlay 운영 중에는 `make ftp-up`을 쓰지 않음 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true -o wide
kubectl --context "<context>" -n etch-ftp get daemonset ftp
kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide
kubectl --context "<context>" -n etch-ftp get events --sort-by=.lastTimestamp
```

성공: DaemonSet DESIRED·CURRENT·READY가 대상 노드 수와 같음, 공통 마무리의 JSON 판정 `0`.

## 멈추고 사람에게 묻는 조건

- `ftp-check`에서 Secret 불일치(기존 계정 파일과 다름), 노드 상태 오류, control plane 선택 거부, `기존 FTP 노드도 FTP_NODES에 포함하세요`
- 노드 포트 점유, `ImagePullBackOff`, FailedMount, 연결 시간 초과(방화벽)
- `kubectl apply -k deploy/ftp/k8s` 직접 적용이 필요해 보이는 경우. 실행하지 않습니다(env가 반영되지 않음).
