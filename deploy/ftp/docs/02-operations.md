# FTP 접속 확인과 운영

[FTP 가이드](../README.md) · [설치 준비와 별도 overlay 배포](01-install.md)

설치·업데이트 절차는 [FTP 가이드](../README.md)에 있습니다. 이 문서는 접속 확인과 그 밖의 운영 작업입니다.
kubectl·make 명령은 관리 호스트의 저장소 루트에서 실행하고 `<context>`에는 대상 Kubernetes context를 넣습니다. 별도 계정 파일·env를 쓰면 [가이드의 입력](../README.md#입력)대로 `FTP_CREDENTIAL_FILE`·`FTP_ENV`를 명령에 붙입니다.

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

FTP 클라이언트 PC에서 접속하고, 이후 접속한 노드에서 파일을 확인합니다.

| 항목 | 값 |
| --- | --- |
| 프로토콜 | FTP |
| 호스트 | 파일을 저장할 FTP 노드의 InternalIP |
| 포트 | 6380 |
| 사용자·비밀번호 | 계정 파일(기본 `deploy/ftp/env/initial-account.env`)의 `FTP_USER`, `FTP_PASS` |
| 전송 모드 | Passive (포트 8076–8079) |
| 로그인 후 업로드 폴더 | `data_movement/` |

구분 가능한 이름의 작은 테스트 파일을 업로드한 뒤 다운로드해 내용이 같은지 확인합니다.
**접속한 노드에서** `/appdata/data_movement/<테스트파일>`이 생겼는지 확인합니다. 다른 FTP 노드도 해당 IP로 같은 검사를 반복하고, 다른 노드의 저장 폴더에 테스트 파일이 생기지 않는 것도 확인합니다.
Pod Ready·렌더 검사·smoke만으로 실제 전송 성공을 대신하지 않습니다.

기존 클라이언트가 Compose의 `ftp` DNS 이름을 사용했다면 대상 노드 IP와 6380으로 바꿉니다. Kubernetes 배포는 이 DNS 이름을 만들지 않습니다.

검증 후 [FTP 서비스 기록](../../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 대상 노드·접속 주소·검증 결과를, [FTP 네트워크 기록](../../shared/docs/infrastructure/network.md#ftp-직접-접속)에 실제 방화벽 확인 결과를 갱신합니다.

## 3. 노드 추가·재배포

1. [사람] 추가 노드에서 [저장 폴더와 포트 확인](01-install.md#3-각-노드의-저장-폴더와-포트-확인)을 수행하고 방화벽을 요청합니다. 없는 `/appdata/data_movement`는 Pod 시작 전에 생성됩니다.
2. [조회] control plane을 추가한다면 사용 중인 env의 `FTP_ALLOW_CONTROL_PLANE`이 `true`인지 확인합니다. [대상 선택 설정](01-install.md#control-plane도-대상에-추가하기)을 따릅니다.
3. [변경] `FTP_NODES`에 기존 노드와 새 노드를 모두 넣어 [가이드 B](../README.md#b-업데이트)의 노드 추가를 실행합니다. 일반 재배포는 `FTP_NODES`를 생략한 같은 명령입니다. 별도 env로 설치했다면 같은 `FTP_ENV`를 붙입니다.

별도 overlay 환경은 가이드의 명령 대신 [overlay 검사](01-install.md#검사와-렌더-확인)와 [적용](01-install.md#선택한-노드-전체에-한-번-적용)을 반복합니다.
`k8s/start.sh`를 바꾸면 ConfigMap 이름이 바뀌어 Pod가 갱신됩니다.

**다음 단계:** 새 노드에서 2단계를 확인합니다.

## 4. 특정 노드에서 중단

[승인] 해당 노드의 FTP 접속이 중단됩니다. 대상 노드와 영향을 확인한 뒤 실행합니다.

```bash
kubectl --context "<context>" label node <중단할 노드 이름> etch.io/ftp-enabled-
kubectl --context "<context>" -n etch-ftp get pods -l app=ftp -o wide
```

**기대 결과:** 해당 노드의 FTP Pod가 제거됩니다. 저장 폴더와 파일은 남고 다른 노드로 이동하지 않습니다.
이후 `FTP_NODES`를 지정할 때는 해당 이름을 뺍니다. 이전 목록으로 `ftp-up`이나 overlay 적용을 실행하면 다시 라벨이 붙습니다.

## 5. 계정 변경

`ftp-up`은 기존 계정을 자동 변경하지 않습니다. 모든 FTP 노드에 영향을 주므로 클라이언트 설정도 함께 갱신합니다.

1. [사람] 계정 파일(기본 `deploy/ftp/env/initial-account.env`)의 `FTP_USER`, `FTP_PASS`를 수정하고 권한 `600`을 유지합니다. 형식은 [계정 파일 준비](01-install.md#4-관리-호스트의-계정-파일-준비)를 따릅니다.
2. [승인] Secret을 교체하고 DaemonSet을 재시작합니다. 노드별로 Pod가 다시 시작되는 동안 그 노드의 접속이 끊깁니다.

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

**다음 단계:** 새 계정으로 각 노드에서 2단계를 다시 확인합니다.

## 6. 문제 해결

[조회]

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
| ImagePullBackOff | `FTP_ENV`(기본 `env/prod.env`)의 `FTP_IMAGE`가 사내 미러 주소인지, 해당 digest 제공 여부·Worker의 CA·registry 접근·`IMAGE_PULL_SECRET` 확인. 수정 후 같은 env로 [가이드 B](../README.md#b-업데이트)의 배포 명령 실행 |
| 시작 실패 | 기존 6380 포트 점유, 계정 형식, 폴더 권한 |
| 연결 시간 초과 | 접속 IP·6380 방화벽·노드 네트워크 |
| 로그인은 되지만 목록·전송 실패 | passive 포트 8076–8079 방화벽, InternalIP 직접 접근, 파일 권한 |
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
