# 01. FTP 서버 설치

[시작 안내](README.md) · 다음: [접속 확인과 운영](02_OPERATIONS.md)

## 1. 실행 위치와 준비물

| 위치 | 필요한 작업 |
| --- | --- |
| 관리 PC 또는 클러스터 관리 서버 | 저장소 checkout, Python 3.10+·Make·Bash·kubectl, kubeconfig 준비, 검사·배포 실행 |
| FTP를 실행할 각 Linux Worker | Kubernetes 등록, 데이터 폴더·기존 파일 권한·포트 준비 |
| FTP 클라이언트 PC | 대상 Worker IP로 접속할 네트워크·FTP 클라이언트 준비 |

관리 호스트에는 루트 Makefile과 `deploy/ftp`, `deploy/shared`가 필요합니다.
선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh ftp`를 사용합니다.
서버 실행에 local 폴더나 앱 소스는 필요하지 않습니다.
kubectl에는 노드 조회·라벨 변경, namespace·Secret·DaemonSet·ConfigMap 적용 및 Pod 조회 권한이 필요합니다.

## 2. 클러스터와 Worker 선택

이후 명령은 **저장소 루트의 동일한 Bash 세션**에서 실행합니다.

```bash
kubectl config get-contexts
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" get nodes -l etch.io/ftp-enabled=true -o wide

read -r -p 'FTP Worker 이름 (여러 개는 쉼표 구분, 공백 없음): ' FTP_NODES
export FTP_NODES
```

`FTP_NODES` 예시는 `worker-a` 또는 `worker-a,worker-b`입니다. IP가 아닌 `NAME` 값을 넣습니다.
**이미 FTP 라벨이 붙은 노드까지 포함한 전체 목록**을 입력합니다. 기존 노드를 목록에서 빼면 검사에서 중단합니다.
노드 제거는 [운영 문서](02_OPERATIONS.md)의 라벨 제거 절차를 먼저 수행합니다.
검사는 Linux Worker, Ready 상태, cordon·차단 taint, IPv4 InternalIP를 확인합니다.

## 3. 각 Worker의 저장 폴더와 포트 준비

이 단계만 **선택한 각 Worker에 접속해서** 수행합니다.

```bash
sudo mkdir -p /data/data_movement
df -h /data/data_movement
sudo ss -lntp | grep -E ':(6380|8076|8077|8078|8079)[[:space:]]' || true
```

기존 파일이 있으면 해당 Worker의 `/data/data_movement`로 이관하고 읽기·쓰기 권한을 맞춥니다.
FTP 시작 시 최상위 폴더 소유자를 이미지의 `ftp` 사용자로 변경하며 하위 파일 소유권은 변경하지 않습니다.
배포 스크립트는 원격 디렉터리를 만들거나 데이터를 옮기지 않습니다. 폴더가 없으면 Pod 기동에 실패합니다.

기존 FTP가 포트를 쓰고 있으면 전환 시 중단합니다. 방화벽은 클라이언트에서 Worker InternalIP의
TCP **6380, 8076–8079**에 접근할 수 있도록 준비합니다. passive 전송 중에는 데이터 포트도 사용합니다.
namespace 정책에서 hostNetwork와 hostPath를 허용해야 합니다.

## 4. 관리 호스트의 계정 파일 준비

Git 저장소 밖의 파일을 만들고 접근 권한을 제한합니다. 아래는 파일 내용을 출력하지 않고 입력받습니다.

```bash
read -r -p 'FTP 계정 파일 절대 경로 (새 파일): ' FTP_CREDENTIAL_FILE
export FTP_CREDENTIAL_FILE
(
  set -e
  umask 077
  set -o noclobber
  read -r -p 'FTP 사용자 이름: ' ftp_login
  read -r -s -p 'FTP 비밀번호: ' ftp_password
  printf '\n'
  printf 'FTP_USER=%s\nFTP_PASS=%s\n' "$ftp_login" "$ftp_password" > "$FTP_CREDENTIAL_FILE"
)
```

이미 계정 파일이 있으면 경로만 지정하고 재생성하지 않습니다. 기존 파일에는 `chmod 600`을 적용합니다.
파일은 `FTP_USER=값`, `FTP_PASS=값` 두 줄입니다. `export`나 값을 감싸는 따옴표를 넣지 않습니다.
사용자 이름은 영문·숫자·밑줄·하이픈, 비밀번호는 비어 있지 않아야 하며 줄바꿈·역슬래시를 넣지 않습니다.
모든 대상 노드는 `etch-ftp/ftp-credentials` Secret을 공유합니다. 기본 계정은 없습니다.

## 5. 검사 후 배포

관리 호스트의 저장소 루트에서 실행합니다. 앞서 export한 세 변수를 사용합니다.

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check
# 위 검사가 통과하고 출력된 context·노드·IP가 맞으면 실행합니다.
make ftp-up
```

| 명령 | 처리 내용 |
| --- | --- |
| `ftp-check` | 계정 형식·권한, 원본 렌더, 대상 노드 상태, 기존 Secret 일치 여부 검사 |
| `ftp-up` | 같은 검사 → namespace 준비 → 없는 Secret 생성 → 노드 라벨 → 스택 적용 → 최대 5분 기동 대기 → Pod 위치 출력 |

기존 Secret이 입력과 다르면 변경 전에 중단합니다. 동일 입력으로 재실행할 수 있고 파일 데이터를 삭제하지 않습니다.
배포 중 실패하면 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 재실행합니다.
스크립트는 `deploy/ftp/scripts/up.py`이며 Python 표준 라이브러리만 사용합니다.
모든 클러스터 명령은 명시한 context를 사용합니다.

이 실행기는 기본 `k8s/` 원본용입니다. 기본 이미지는 digest로 고정된 `fauria/vsftpd`입니다.
사내 registry·imagePullSecrets나 다른 저장 경로가 필요하면 [수동 배포·overlay 절차](03_KUBERNETES.md)를 사용합니다.
검사 통과는 이미지 pull·원격 디스크·방화벽·실제 FTP 인증 성공을 보장하지 않습니다.

## 6. 완료 확인

[접속 확인과 운영](02_OPERATIONS.md)의 업로드·다운로드 검증까지 수행하면 설치가 완료됩니다.
현재 구성은 IPv4 직접 접속과 passive 모드용이며 Service·Ingress·VIP를 만들지 않습니다.
TLS나 NAT 주소를 자동 설정하지 않습니다.
