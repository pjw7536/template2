# 서버별 FTP 배포

[배포 문서 안내](../README.md)

FTP가 필요한 Linux Worker에 `etch.io/ftp-enabled=true` 라벨을 붙이면 DaemonSet이
노드마다 Pod 하나를 실행합니다. `hostNetwork`로 해당 노드 IP에 직접 접속하며
Service·Ingress·VIP를 사용하지 않습니다. Kubernetes에 등록되지 않은 서버에는 배치되지 않습니다.

| 항목 | 설정 |
| --- | --- |
| 접속 주소 | 대상 노드 InternalIP, TCP 6380 |
| Passive 주소 | Downward API의 `status.hostIP` |
| Passive 포트 | TCP 8076–8079 |
| 노드 저장 폴더 | `/data/data_movement` |
| 컨테이너 저장 폴더 | `/data/data_movement` |
| 로그인 후 업로드 경로 | `data_movement/` |
| 계정 | `etch-ftp` namespace의 `ftp-credentials` Secret |

노드별 파일은 독립적이며 자동 복제·이동하지 않습니다. 소비 앱이 다른 노드에 있으면
별도 공유 저장소 또는 파일 전송이 필요합니다. 기존 Compose의 `ftp` DNS 이름은 생성하지 않으므로
기존 클라이언트의 접속 설정을 대상 노드 IP와 6380으로 변경합니다.
외부 PC용 Compose와 이전 사내 Compose 참고 자료는 그대로 유지합니다.

## 준비

1. 선택 체크아웃이면 `bash deploy/shared/scripts/checkout-server.sh ftp`를 실행합니다.
2. 각 대상 Worker에서 `/data/data_movement`를 준비하고 기존 데이터를 이관합니다.
   없는 경로는 자동 생성하지 않습니다. 시작 스크립트는 최상위 폴더 소유자를 이미지의 `ftp` 사용자로 변경합니다.
   하위 파일의 소유권은 변경하지 않으므로 기존 데이터의 읽기·쓰기 권한을 별도로 맞춥니다.
3. 기존 FTP가 해당 포트를 점유하고 있으면 중단합니다. 클라이언트에서 노드 InternalIP의
   TCP 6380과 8076–8079에 접근할 수 있도록 방화벽을 설정합니다.
   이 구성은 IPv4 직접 접속·passive 모드 기준이며 NAT 주소나 TLS를 자동 설정하지 않습니다.
4. 기본 이미지는 기존 FTP와 같은 `fauria/vsftpd`이며 접속 검증한 digest로 고정합니다. 사내 반입 시 외부 overlay의
   Kustomize `images`로 승인된 registry 주소와 검증한 digest를 지정합니다.
   실제 배포도 동일한 overlay를 사용하고 필요한 imagePullSecrets를 추가합니다.

기본 경로가 다른 서버는 같은 목적의 경로를 준비하거나, 별도 overlay에서 hostPath와
노드 선택 라벨·DaemonSet 이름을 함께 변경해 서로 겹치지 않는 노드 그룹으로 배포합니다.
hostNetwork와 hostPath를 허용하는 namespace 정책이 필요합니다.

## 적용

아래 명령은 명시한 클러스터에 적용합니다. 예시의 context와 노드 이름을 실제 값으로 지정합니다.
대상 노드 라벨이 없으면 FTP Pod가 실행되지 않습니다.

```bash
make server-check APP=ftp
read -r -p '대상 Kubernetes context: ' FTP_CONTEXT
read -r -p 'FTP를 실행할 Worker 이름: ' FTP_NODE
kubectl --context "$FTP_CONTEXT" create namespace etch-ftp --dry-run=client -o yaml | kubectl --context "$FTP_CONTEXT" apply -f -

# 외부 파일에는 FTP_USER와 FTP_PASS만 기록하고 접근 권한을 600으로 제한합니다.
read -r -p 'FTP 계정 env 파일 절대 경로: ' FTP_CREDENTIAL_FILE
kubectl --context "$FTP_CONTEXT" -n etch-ftp create secret generic ftp-credentials \
  --from-env-file="$FTP_CREDENTIAL_FILE" --dry-run=client -o yaml | kubectl --context "$FTP_CONTEXT" apply -f -
kubectl --context "$FTP_CONTEXT" label node "$FTP_NODE" etch.io/ftp-enabled=true --overwrite
kubectl --context "$FTP_CONTEXT" apply -k deploy/ftp/k8s
kubectl --context "$FTP_CONTEXT" -n etch-ftp rollout status daemonset/ftp
kubectl --context "$FTP_CONTEXT" -n etch-ftp get pods -o wide
```

FTP_USER는 영문·숫자·밑줄·하이픈만 사용하고 FTP_PASS에는 줄바꿈·역슬래시를 넣지 않습니다.
기본 계정은 제공하지 않습니다. 현재 모든 대상 노드는 같은 Secret을 사용합니다.
계정 변경 후에는 `kubectl --context "$FTP_CONTEXT" -n etch-ftp rollout restart daemonset/ftp`를 실행합니다.

각 노드 IP의 6380에 FTP 클라이언트로 로그인하고 passive 모드로 `data_movement/`에
테스트 파일을 업로드·다운로드합니다. 대상 노드의 실제 폴더에만 파일이 생겼는지 확인합니다.
원본 검사와 렌더링만으로 실제 포트 연결·인증·저장 성공을 보장하지 않습니다.

## 중단

특정 노드에서만 중단하려면 라벨을 제거합니다. 데이터 폴더와 파일은 남습니다.

```bash
kubectl --context "$FTP_CONTEXT" label node "$FTP_NODE" etch.io/ftp-enabled-
```

## 원본

- `k8s/stack.yaml`: namespace·DaemonSet·Secret 참조·노드 폴더 마운트
- `k8s/start.sh`: 기존 포트와 저장 경로 적용, 기본 계정 실행 방지
- `k8s/kustomization.yaml`: 스크립트 변경 시 Pod가 갱신되는 ConfigMap 생성

설계 근거: [Kubernetes DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/),
[vsftpd 이미지 시작 스크립트](https://github.com/fauria/docker-vsftpd/blob/master/run-vsftpd.sh).
