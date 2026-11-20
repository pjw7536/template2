# FTP 접속 확인과 운영

[FTP 가이드](../README.md) · [설치 준비와 별도 overlay 배포](01-install.md)

설치·업데이트 절차는 [FTP 가이드](../README.md)에 있습니다. 이 문서는 접속 확인과 그 밖의 운영 작업입니다.
kubectl·make 명령은 관리 호스트의 저장소 루트에서 실행하고 `<context>`에는 대상 Kubernetes context를 넣습니다. 별도 계정 파일·env를 쓰면 [가이드의 입력](../README.md#입력)대로 `FTP_CREDENTIAL_FILE`·`FTP_ENV`를 명령에 붙입니다. 노드에서 실행하는 명령은 관리 호스트에서 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행) 절의 도구로 전달합니다.

- [1. Pod가 뜬 서버 확인](#1-pod가-뜬-서버-확인)
- [2. 업로드·다운로드 확인](#2-업로드다운로드-확인)
- [3. 노드 추가·재배포](#3-노드-추가재배포)
- [4. 특정 노드에서 중단](#4-특정-노드에서-중단)
- [5. 계정 변경](#5-계정-변경)
- [6. 문제 해결](#6-문제-해결)
- [실행 계약과 원본 파일](#실행-계약과-원본-파일)

## 1. Pod가 뜬 서버 확인

[조회]

```bash
kubectl --context "<context>" get nodes -l etch.io/ftp-enabled=true -o wide
kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide
kubectl --context "<context>" -n etch-ftp get daemonset ftp
```

**기대 결과:** 노드 목록의 `INTERNAL-IP`가 접속 주소, Pod 목록의 `NODE`가 실제 실행 서버입니다. DaemonSet의 `DESIRED`, `CURRENT`, `READY`가 대상 노드 수와 같습니다.

## 2. 업로드·다운로드 확인

대상 노드마다 FTP로 접속해 파일을 올리고 받은 뒤, 접속한 노드에서 파일을 확인합니다. 접속 값은 다음과 같습니다.

| 항목 | 값 |
| --- | --- |
| 프로토콜 | FTP |
| 호스트 | 파일을 저장할 FTP 노드의 InternalIP |
| 포트 | 6380 |
| 사용자·비밀번호 | 계정 파일(기본 `deploy/ftp/env/initial-account.env`)의 `FTP_USER`, `FTP_PASS` |
| 전송 모드 | Passive (포트 8076–8079) |
| 로그인 후 업로드 폴더 | `data_movement/` |

1. [변경] 관리 호스트의 저장소 루트에서 작은 테스트 파일을 올리고 다시 받아 내용을 비교합니다. `<노드 InternalIP>`는 [1. Pod가 뜬 서버 확인](#1-pod가-뜬-서버-확인)의 노드 목록에 나온 `INTERNAL-IP`, `<노드>`는 그 노드 이름입니다. 계정은 명령에 직접 쓰지 않고 계정 파일에서 읽습니다. 다른 계정 파일을 쓰면 `deploy/ftp/env/initial-account.env`를 그 경로로 바꿉니다.
   ```bash
   printf 'ftp-test\n' > /tmp/ftp-test-<노드>.txt
   curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
     --user "$(sed -n 's/^FTP_USER=//p' deploy/ftp/env/initial-account.env):$(sed -n 's/^FTP_PASS=//p' deploy/ftp/env/initial-account.env)" \
     -T /tmp/ftp-test-<노드>.txt "ftp://<노드 InternalIP>:6380/data_movement/ftp-test-<노드>.txt"
   curl --fail --silent --show-error --connect-timeout 5 --max-time 30 \
     --user "$(sed -n 's/^FTP_USER=//p' deploy/ftp/env/initial-account.env):$(sed -n 's/^FTP_PASS=//p' deploy/ftp/env/initial-account.env)" \
     -o /tmp/ftp-test-<노드>.down "ftp://<노드 InternalIP>:6380/data_movement/ftp-test-<노드>.txt"
   cmp /tmp/ftp-test-<노드>.txt /tmp/ftp-test-<노드>.down && echo 'FTP 업로드·다운로드 확인 완료'
   ```
   성공: `FTP 업로드·다운로드 확인 완료`. 로그인 오류면 계정 파일이 Secret과 같은지, 시간 초과면 passive 포트 8076–8079까지의 경로를 [6. 문제 해결](#6-문제-해결)로 확인합니다.
2. [조회] **접속한 노드에서** 파일이 생겼는지 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)으로 확인합니다.
   ```bash
   python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'ls -l /appdata/data_movement/ftp-test-<노드>.txt'
   ```
   성공: 파일이 조회됩니다. 다른 FTP 노드도 해당 IP로 1~2를 반복하고, 다른 노드의 저장 폴더에는 이 파일이 없는 것도 같은 명령으로 확인합니다(`No such file`과 `노드 명령 실패`).
3. [변경] 시험 파일을 같은 계정의 FTP 삭제로 지우고 남은 목록을 조회합니다.
   ```bash
   curl --fail --silent --show-error --connect-timeout 5 --max-time 30 --list-only \
     --user "$(sed -n 's/^FTP_USER=//p' deploy/ftp/env/initial-account.env):$(sed -n 's/^FTP_PASS=//p' deploy/ftp/env/initial-account.env)" \
     -Q "DELE data_movement/ftp-test-<노드>.txt" "ftp://<노드 InternalIP>:6380/data_movement/"
   ```
   성공: 출력된 목록에 `ftp-test-<노드>.txt`가 없습니다. 다른 파일은 지우지 않습니다.

위 시험은 관리 호스트를 출발지로 한 로그인·passive 전송을 확인합니다. 실제 파일 전송 클라이언트 출발지에서의 접속은 [방화벽](../../shared/docs/infrastructure/access.md#방화벽) 절의 `완료 확인`으로 확인하고, 클라이언트 PC에서만 확인할 수 있는 항목은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절을 따릅니다.
Pod Ready·렌더 검사·smoke만으로 실제 전송 성공을 대신하지 않습니다.

기존 클라이언트가 Compose의 `ftp` DNS 이름을 사용했다면 대상 노드 IP와 6380으로 바꿉니다. Kubernetes 배포는 이 DNS 이름을 만들지 않습니다.

검증 후 [FTP 서비스 기록](../../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 대상 노드·접속 주소·검증 결과를, [FTP 네트워크 기록](../../shared/docs/infrastructure/network.md#ftp-직접-접속)에 실제 방화벽 확인 결과를 갱신합니다.

## 3. 노드 추가·재배포

1. [조회] 추가 노드에서 [저장 폴더와 포트 확인](01-install.md#3-각-노드의-저장-폴더와-포트-확인)을 수행합니다. [변경] 새 노드의 6380·8076–8079가 허용 출발지에서 열려 있지 않으면 [방화벽](../../shared/docs/infrastructure/access.md#방화벽) 절의 방법으로 엽니다. 없는 `/appdata/data_movement`는 Pod 시작 전에 생성됩니다.
2. [조회] control plane을 추가한다면 사용 중인 env의 `FTP_ALLOW_CONTROL_PLANE`이 `true`인지 확인합니다. [대상 선택 설정](01-install.md#control-plane도-대상에-추가하기)을 따릅니다.
3. [변경] `FTP_NODES`에 기존 노드와 새 노드를 모두 넣어 [가이드 B](../README.md#b-업데이트)의 노드 추가를 실행합니다. 일반 재배포는 `FTP_NODES`를 생략한 같은 명령입니다. 별도 env로 설치했다면 같은 `FTP_ENV`를 붙입니다.

별도 overlay 환경은 가이드의 명령 대신 [overlay 검사](01-install.md#검사와-렌더-확인)와 [적용](01-install.md#선택한-노드-전체에-한-번-적용)을 반복합니다.
`k8s/start.sh`를 바꾸면 ConfigMap 이름이 바뀌어 Pod가 갱신됩니다.

**다음 단계:** 새 노드에서 2단계를 확인합니다.

## 4. 특정 노드에서 중단

[승인] 해당 노드의 FTP 접속이 중단됩니다. 대상 노드와 영향을 보여 주고 승인받은 뒤 실행합니다.

```bash
kubectl --context "<context>" label node <중단할 노드 이름> etch.io/ftp-enabled-
kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide
```

**기대 결과:** `node/<중단할 노드 이름> unlabeled`가 나오고 Pod 목록에서 해당 노드의 FTP Pod가 사라집니다(종료 중이면 잠시 `Terminating`). 저장 폴더와 파일은 남고 다른 노드로 이동하지 않습니다.
이후 `FTP_NODES`를 지정할 때는 해당 이름을 뺍니다. 이전 목록으로 `ftp-up`이나 overlay 적용을 실행하면 다시 라벨이 붙습니다.

## 5. 계정 변경

`ftp-up`은 기존 계정을 자동 변경하지 않습니다. 모든 FTP 노드에 영향을 주므로 클라이언트 설정도 함께 갱신합니다.

1. [변경] 새 계정 파일을 준비합니다. 새 `FTP_USER`, `FTP_PASS` 값은 요청에 주어지는 입력이며 명령이나 보고에 쓰지 않습니다. [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 위치에 [계정 파일 형식](01-install.md#4-관리-호스트의-계정-파일-준비)의 파일을 두고 권한 `600`을 적용합니다. 저장소의 계정 파일을 고치지 않습니다.
2. [검사] 파일의 키와 권한을 확인합니다. 값은 출력하지 않습니다.
   ```bash
   stat -c '%a %n' <계정 파일 경로>
   grep -c -E '^(FTP_USER|FTP_PASS)=.' <계정 파일 경로>
   ```
   성공: 권한 `600`, 줄 수 `2`.
3. [승인] Secret을 교체하고 DaemonSet을 재시작합니다. 노드별로 Pod가 다시 시작되는 동안 그 노드의 접속이 끊깁니다. 대상과 영향을 보여 주고 승인받은 뒤 아래 블록을 실행합니다.

```bash
(
  set -euo pipefail
  kubectl --context "<context>" -n etch-ftp create secret generic ftp-credentials \
    --from-env-file="<계정 파일 경로>" --dry-run=client -o yaml | \
    kubectl --context "<context>" apply --server-side --field-manager=ftp-credentials -f -
  kubectl --context "<context>" -n etch-ftp rollout restart daemonset/ftp
  kubectl --context "<context>" -n etch-ftp rollout status daemonset/ftp --timeout=300s
)
```

**기대 결과:** `daemon set "ftp" successfully rolled out`.
이후 검사·배포 명령(`make ops-deploy APP=ftp`, `make ftp-check`, `make ftp-up`)에는 항상 `FTP_CREDENTIAL_FILE=<계정 파일 경로>`를 붙입니다. 붙이지 않으면 기본 계정 파일과 Secret이 달라 검사가 멈춥니다. 새 파일 경로는 [운영 위치](../../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다.

**다음 단계:** 새 계정 파일로 각 노드에서 [2. 업로드·다운로드 확인](#2-업로드다운로드-확인)을 다시 수행합니다.

## 6. 문제 해결

[조회] 이벤트와 Pod 상태·로그를 봅니다. 한 번에 모으려면 [장애 조회](../../README.md#장애-조회)의 `make ops-diagnose APP=ftp KUBE_CONTEXT="<context>"`를 씁니다.

```bash
kubectl --context "<context>" -n etch-ftp get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n etch-ftp describe pod <FTP Pod 이름>
kubectl --context "<context>" -n etch-ftp logs <FTP Pod 이름> --tail=100
```

| 증상 | 확인할 내용 |
| --- | --- |
| Pod가 없음 | 대상 노드의 FTP 라벨·Linux 라벨 |
| Control plane 선택 거부 | 사용 중인 `FTP_ENV`의 `FTP_ALLOW_CONTROL_PLANE=true` 확인. 역할 NoSchedule 외 taint·cordon·NotReady는 별도 해결 필요 |
| Pending / FailedMount | 노드 상태·taint, 디스크·경로 생성 권한, `/appdata/data_movement`가 파일로 점유됐는지, namespace 정책 |
| ImagePullBackOff | `FTP_ENV`(기본 `env/prod.env`)의 `FTP_IMAGE`가 사내 미러 주소인지, 해당 digest 제공 여부·Worker의 CA·registry 접근·`IMAGE_PULL_SECRET` 확인. Worker에서의 확인은 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo -n crictl pull <FTP_IMAGE 값>'`. 다른 이미지 주소가 필요하면 저장소 밖 env 사본에서 바꾼 뒤 같은 `FTP_ENV`로 [가이드 B](../README.md#b-업데이트)의 배포 명령 실행 |
| 시작 실패 | 기존 6380 포트 점유, 계정 형식, 폴더 권한. 포트는 [저장 폴더와 포트 확인](01-install.md#3-각-노드의-저장-폴더와-포트-확인)의 명령으로 조회 |
| 연결 시간 초과 | 접속 IP·6380 방화벽·노드 네트워크. [방화벽](../../shared/docs/infrastructure/access.md#방화벽) 절의 `찾는 방법`으로 출발지에서 확인 |
| 로그인은 되지만 목록·전송 실패 | passive 포트 8076–8079 방화벽([방화벽](../../shared/docs/infrastructure/access.md#방화벽)), InternalIP 직접 접근, 파일 권한 |
| 다른 서버에서 파일이 안 보임 | 파일을 업로드한 IP의 노드 확인. 노드별 저장은 독립적 |

## 실행 계약과 원본 파일

| 항목 | 설정 |
| --- | --- |
| 접속 주소 | 대상 노드 InternalIP, TCP 6380 (`hostNetwork`) |
| Passive 주소·포트 | Downward API의 `status.hostIP`, TCP 8076–8079 |
| 노드 저장 폴더 | `/appdata/data_movement` (`DirectoryOrCreate`) |
| 컨테이너 저장 폴더 | `/data/data_movement`, 로그인 후 경로 `data_movement/` |
| 계정 | `etch-ftp` namespace의 `ftp-credentials` Secret |
| 노드 선택 | `etch.io/ftp-enabled=true`, `kubernetes.io/os=linux` |

- `k8s/stack.yaml`: namespace·DaemonSet·Secret 참조·노드 폴더 마운트
- `k8s/start.sh`: 접속 포트와 저장 경로 적용, 기본 계정 실행 방지
- `k8s/kustomization.yaml`: 스크립트 변경 시 Pod가 갱신되는 ConfigMap 생성
- `scripts/up.py`: `ftp-check`·`ftp-up` 실행기. Python 표준 라이브러리만 사용

설계 근거: [Kubernetes DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/), [vsftpd 이미지 시작 스크립트](https://github.com/fauria/docker-vsftpd/blob/master/run-vsftpd.sh).
