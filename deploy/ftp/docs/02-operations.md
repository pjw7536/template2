# FTP 접속 확인과 운영

[앱 안내](../README.md) · [설치](01-install.md)

**실행 위치:** kubectl 명령은 관리 호스트의 저장소 루트에서 설치 때 선택한 `KUBE_CONTEXT`로 실행합니다.
새 Bash 세션에서는 `KUBE_CONTEXT`, `FTP_NODES`, [계정 파일](01-install.md#4-관리-호스트의-계정-파일-준비)의 절대 경로 `FTP_CREDENTIAL_FILE`, 별도 env를 쓰면 `FTP_ENV`를 다시 export합니다.

## 1. Pod가 뜬 서버 확인

```bash
kubectl --context "$KUBE_CONTEXT" get nodes -l etch.io/ftp-enabled=true -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get pods -l app=ftp -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get daemonset ftp
```

**기대 결과:** 노드 목록의 `INTERNAL-IP`가 접속 주소, Pod 목록의 `NODE`가 실제 실행 서버입니다. DaemonSet의 `DESIRED`, `CURRENT`, `READY`가 대상 노드 수와 같습니다.

## 2. 업로드·다운로드 확인

**실행 위치:** FTP 클라이언트 PC, 이후 접속한 노드.

| 항목 | 값 |
| --- | --- |
| 프로토콜 | FTP |
| 호스트 | 파일을 저장할 FTP 노드의 InternalIP |
| 포트 | 6380 |
| 사용자·비밀번호 | `FTP_CREDENTIAL_FILE`의 `FTP_USER`, `FTP_PASS` |
| 전송 모드 | Passive (포트 8076–8079) |
| 로그인 후 업로드 폴더 | `data_movement/` |

구분 가능한 이름의 작은 테스트 파일을 업로드한 뒤 다운로드해 내용이 같은지 확인합니다.
**접속한 노드에서** `/appdata/data_movement/<테스트파일>`이 생겼는지 확인합니다. 다른 FTP 노드도 해당 IP로 같은 검사를 반복합니다.

기존 클라이언트가 Compose의 `ftp` DNS 이름을 사용했다면 대상 노드 IP와 6380으로 바꿉니다. Kubernetes 배포는 이 DNS 이름을 만들지 않습니다.

## 3. 노드 추가·재배포

1. 추가 노드에서 [저장 폴더와 포트 확인](01-install.md#3-각-노드의-저장-폴더와-포트-확인)을 수행하고 방화벽을 요청합니다. 없는 `/appdata/data_movement`는 Pod 시작 전에 생성됩니다.
2. control plane을 추가한다면 사용 중인 env의 `FTP_ALLOW_CONTROL_PLANE`이 `true`인지 확인합니다. [대상 선택 설정](01-install.md#control-plane도-대상에-추가하기)을 따릅니다.
3. `FTP_NODES`를 기존 노드와 새 노드를 모두 포함한 목록으로 갱신하고 배포합니다.

기본 배포 환경은 아래 명령을 사용합니다. 일반 재배포도 같습니다. 별도 env로 설치했다면 같은 `FTP_ENV`를 지정합니다.

```bash
export FTP_NODES=worker-a,worker-b
make ftp-check
make ftp-up
```

예시 노드 이름은 실제 값으로 바꿉니다. 별도 overlay 환경은 [overlay 검사·적용](01-install.md#5-2-검사와-렌더-확인)의 5-2~5-3을 반복합니다.
`k8s/start.sh`를 바꾸면 ConfigMap 이름이 바뀌어 Pod가 갱신됩니다.

**다음 단계:** 새 노드에서 2단계를 확인합니다.

## 4. 특정 노드에서 중단

```bash
read -r -p 'FTP를 중단할 노드 이름: ' FTP_STOP_NODE
kubectl --context "$KUBE_CONTEXT" label node "$FTP_STOP_NODE" etch.io/ftp-enabled-
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get pods -l app=ftp -o wide
```

**기대 결과:** 해당 노드의 FTP Pod가 제거됩니다. 저장 폴더와 파일은 남고 다른 노드로 이동하지 않습니다.
이후 `FTP_NODES`에서도 해당 이름을 뺍니다. 이전 목록으로 `ftp-up`이나 overlay 적용을 실행하면 다시 라벨이 붙습니다.

## 5. 계정 변경

`ftp-up`은 기존 계정을 자동 변경하지 않습니다. `FTP_CREDENTIAL_FILE`의 `FTP_USER`, `FTP_PASS`를 수정하고 권한 `600`을 유지한 뒤 실행합니다.
모든 FTP 노드에 영향을 주므로 클라이언트 설정도 함께 갱신합니다.

```bash
(
  set -euo pipefail
  kubectl --context "$KUBE_CONTEXT" -n etch-ftp create secret generic ftp-credentials \
    --from-env-file="$FTP_CREDENTIAL_FILE" --dry-run=client -o yaml | \
    kubectl --context "$KUBE_CONTEXT" apply --server-side --field-manager=ftp-credentials -f -
  kubectl --context "$KUBE_CONTEXT" -n etch-ftp rollout restart daemonset/ftp
  kubectl --context "$KUBE_CONTEXT" -n etch-ftp rollout status daemonset/ftp --timeout=300s
)
```

**다음 단계:** 새 계정으로 각 노드에서 2단계를 다시 확인합니다.

## 6. 문제 해결

```bash
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get events --sort-by=.lastTimestamp
read -r -p '확인할 FTP Pod 이름: ' FTP_POD
kubectl --context "$KUBE_CONTEXT" -n etch-ftp describe pod "$FTP_POD"
kubectl --context "$KUBE_CONTEXT" -n etch-ftp logs "$FTP_POD" --tail=100
```

| 증상 | 확인할 내용 |
| --- | --- |
| Pod가 없음 | 대상 노드의 FTP 라벨·Linux 라벨 |
| Control plane 선택 거부 | 사용 중인 `FTP_ENV`의 `FTP_ALLOW_CONTROL_PLANE=true` 확인. 역할 NoSchedule 외 taint·cordon·NotReady는 별도 해결 필요 |
| Pending / FailedMount | 노드 상태·taint, 디스크·경로 생성 권한, `/appdata/data_movement`가 파일로 점유됐는지, namespace 정책 |
| ImagePullBackOff | `FTP_ENV`(기본 `env/prod.env`)의 `FTP_IMAGE`가 사내 미러 주소인지, 해당 digest 제공 여부·Worker의 CA·registry 접근·`IMAGE_PULL_SECRET` 확인. 수정 후 같은 env로 `ftp-check` → `ftp-up` 실행 |
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
