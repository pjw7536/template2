# 02. FTP 접속 확인과 운영

[시작 안내](README.md) · [서버 설치](01_SERVER_SETUP.md) · [원본](03_KUBERNETES.md)

모든 kubectl 명령에는 설치 때 선택한 `KUBE_CONTEXT`를 사용합니다.

## 1. Pod가 뜬 서버 확인

```bash
kubectl --context "$KUBE_CONTEXT" get nodes -l etch.io/ftp-enabled=true -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get pods -l app=ftp -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get daemonset ftp
```

노드 목록의 `INTERNAL-IP`가 접속 주소이고 Pod 목록의 `NODE`가 실제 실행 서버입니다.
DaemonSet의 `DESIRED`, `CURRENT`, `READY`가 대상 노드 수와 일치하는지 확인합니다.

## 2. 업로드·다운로드 확인

FTP 클라이언트에 다음 값을 입력합니다.

| 항목 | 값 |
| --- | --- |
| 프로토콜 | FTP |
| 호스트 | 파일을 저장할 Worker의 InternalIP |
| 포트 | 6380 |
| 사용자·비밀번호 | 설치 시 계정 파일의 값 |
| 전송 모드 | Passive |
| 로그인 후 업로드 폴더 | `data_movement/` |

구분 가능한 이름의 작은 테스트 파일을 업로드한 뒤 다운로드해서 내용이 같은지 확인합니다.
**접속한 Worker에서** `/data/data_movement/<테스트파일>`이 생겼는지 확인합니다.
다른 Worker에도 FTP가 있으면 해당 IP로 별도 접속해 반복합니다. A에 올린 파일이 B에 자동 생성되지는 않습니다.
기존 Compose의 `ftp` DNS 이름 대신 대상 Worker IP와 6380을 사용합니다.

## 3. 노드 추가·재배포

추가 Worker의 폴더·포트를 준비한 뒤 `FTP_NODES`를 기존 노드와 새 노드를 모두 포함하도록 갱신합니다.

```bash
export FTP_NODES=worker-a,worker-b
make ftp-check
make ftp-up
```

예시 노드 이름을 실제 값으로 바꿉니다. 일반 재배포도 같은 명령을 사용합니다.
`k8s/start.sh` 변경은 ConfigMap 이름 변경으로 Pod를 갱신합니다.

## 4. 특정 노드에서 중단

```bash
read -r -p 'FTP를 중단할 Worker 이름: ' FTP_STOP_NODE
kubectl --context "$KUBE_CONTEXT" label node "$FTP_STOP_NODE" etch.io/ftp-enabled-
kubectl --context "$KUBE_CONTEXT" -n etch-ftp get pods -l app=ftp -o wide
```

해당 노드의 FTP Pod가 제거됩니다. 저장 폴더와 파일은 남고 다른 노드로 이동하지 않습니다.
이후 `FTP_NODES`에서도 해당 이름을 빼세요. 이전 목록으로 `ftp-up`을 실행하면 다시 라벨이 붙습니다.

## 5. 계정 변경

`ftp-up`은 기존 계정을 자동 변경하지 않습니다. 의도적으로 변경할 때 외부 계정 파일을 먼저 수정한 뒤 실행합니다.
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

새 계정으로 각 노드의 전송을 다시 확인합니다.

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
| Pending / FailedMount | 노드 상태·taint, 해당 노드의 `/data/data_movement` 존재, namespace 정책 |
| ImagePullBackOff | registry 접근·이미지 반입·imagePullSecrets |
| 시작 실패 | 기존 6380 포트 점유, 계정 형식, 폴더 권한 |
| 연결 시간 초과 | 접속 IP·6380 방화벽·노드 네트워크 |
| 로그인은 되지만 목록·전송 실패 | passive 포트 8076–8079 방화벽, InternalIP 직접 접근, 파일 권한 |
| 다른 서버에서 파일이 안 보임 | 파일을 업로드한 IP의 노드 확인. 노드별 저장은 독립적 |
