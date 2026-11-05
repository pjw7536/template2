# 01. FTP 서버 설치

[시작 안내](README.md) · 다음: [접속 확인과 운영](02_OPERATIONS.md)

한 번의 DaemonSet 배포로 선택한 각 Linux 노드에 FTP Pod 하나씩 실행합니다.
기본 대상은 Worker이며 control plane도 아래의 명시적 허용 절차로 추가할 수 있습니다.
**각 대상 노드에서는 디스크·포트를 준비하고, CP1에서는 검사·배포를 한 번 실행**합니다.
사내 미러 이미지는 이 문서의 5절에 따라 배포합니다. 별도 이미지·저장 경로 overlay를 운영하면
1~4절을 마친 뒤 [수동 overlay 적용](03_KUBERNETES.md#사내-이미지로-각-worker에-배포)을 진행합니다.

## 1. 실행 위치와 준비물

| 위치 | 필요한 작업 |
| --- | --- |
| 관리 PC 또는 클러스터 관리 서버 | 저장소 checkout, Python 3.10+·Make·Bash·kubectl, kubeconfig 준비, 검사·배포 실행 |
| FTP를 실행할 각 Linux 노드 | Kubernetes 등록, 저장 디스크·기존 파일 권한·포트 확인. 없는 데이터 폴더는 자동 생성 |
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

read -r -p 'FTP 노드 이름 (여러 개는 쉼표 구분, 공백 없음): ' FTP_NODES
export FTP_NODES
```

`FTP_NODES`에는 노드 목록의 `NAME` 값을 넣습니다. 예를 들어 `worker-a` 또는 `worker-a,worker-b`처럼 지정합니다.

이미 FTP 라벨이 붙은 노드까지 포함한 전체 목록을 입력합니다. 기존 노드를 목록에서 빼면 검사에서 중단합니다.
노드 제거는 [운영 문서](02_OPERATIONS.md)의 라벨 제거 절차를 먼저 수행합니다.

검사는 Linux·Ready 상태, cordon·차단 taint, IPv4 InternalIP를 확인합니다.

### Control plane도 대상에 추가하기

[env/prod.env](env/prod.env) 또는 사용 중인 `FTP_ENV` 파일에서 아래 값을 변경합니다.
계정 파일에 넣는 설정은 아닙니다.

```dotenv
FTP_ALLOW_CONTROL_PLANE=true
```

`FTP_NODES`에는 기존 FTP 노드 전체와 추가할 control plane의 실제 노드 이름을 함께 넣습니다.
기본값과 기존 env에서 이 키를 생략한 값은 `false`입니다. true로 바꿔도 모든 control plane에 자동 설치하지 않습니다.
control-plane·master 역할의 `NoSchedule` taint만 FTP Pod의 toleration으로 허용합니다.
역할 라벨·taint를 제거하지 않으며, 다른 `NoSchedule`·모든 `NoExecute`, cordon·NotReady는 계속 차단합니다.
수동 overlay를 사용하면 [control plane toleration 패치](03_KUBERNETES.md#control-plane을-포함하는-수동-overlay)를 함께 추가합니다.

### 현재 서버 기록을 사용한 대상 선택 예시

아래는 [서버 목록](../shared/docs/infrastructure/servers.md)의 기록을 이용한 **선택 예시**이며 FTP 배포 완료 목록이 아닙니다.
실제 노드명·InternalIP는 위 조회 결과로 대조합니다.

| 선택 대상 | FTP 접속 예시 | 이 노드에서 사용할 폴더 |
| --- | --- | --- |
| `khplanew01` | `10.172.40.117:6380` | `/appdata/data_movement` |
| `khplane01w09` | `10.172.40.87:6380` | `/appdata/data_movement` |

`khplanew01` 한 대만 선택하면 입력값은 `khplanew01`, 두 Worker 모두 선택하면 `khplanew01,khplane01w09`입니다.
`khplane01w09`는 Keycloak 전용 Worker로 기록되어 있으므로 이곳에도 파일 수신이 필요할 때 포함합니다.
CP1~CP3는 관리·제어면 역할입니다. 이곳의 파일 수신이 필요하면 위 옵션을 켜고 실제 노드 이름을 명시적으로 추가합니다.

배포는 노드별로 명령을 반복하지 않습니다. 선택한 전체 노드 이름을 `FTP_NODES`에 넣고 관리 호스트에서 한 번 적용합니다.

## 3. 각 Worker의 저장소와 포트 확인

이 단계만 **선택한 각 노드에 접속해서** 수행합니다. control plane을 포함했다면 해당 노드도 확인합니다.
기존 `/data/data_movement`에서 경로를 바꾼다면 [Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)을 먼저 수행합니다.
그대로 재배포하면 새 빈 폴더를 사용할 수 있으므로 파일 복사와 소비 앱의 호스트 경로 연결을 먼저 확인합니다.

```bash
hostname
ip -br address
if [[ -d /appdata/data_movement ]]; then
  df -h /appdata/data_movement
  sudo stat -c '%U:%G %a %n' /appdata/data_movement
else
  # 저장 폴더는 Pod 배포 시 생성합니다. 사용할 디스크의 여유를 확인합니다.
  df -h /appdata 2>/dev/null || df -h /
fi
sudo ss -lntp | grep -E ':(6380|8076|8077|8078|8079)[[:space:]]' || true
```

예를 들어 `khplanew01`을 선택했다면 그 서버에 SSH 접속해 실행하고, `khplane01w09`도 선택했다면 그 서버에서도 같은 준비를 합니다.
SSH 계정·포트는 운영 접속 정보를 사용합니다. Worker의 저장 디스크·기존 파일 권한·포트는 해당 서버에서 확인합니다.

기존 파일이 있으면 해당 Worker의 `/appdata/data_movement`로 이관하고 읽기·쓰기 권한을 맞춥니다.
FTP 시작 시 최상위 폴더 소유자를 이미지의 `ftp` 사용자로 변경하며 하위 파일 소유권은 변경하지 않습니다.

`hostPath.type=DirectoryOrCreate` 설정으로 kubelet이 Pod 시작 전에 없는 `/appdata/data_movement`를 자동 생성합니다.
수동 `mkdir`은 필수가 아닙니다. 기존 폴더와 파일은 재생성하지 않으며 데이터 이관은 별도로 수행합니다.
새 폴더는 kubelet이 0755 권한으로 생성하고, FTP 시작 시 최상위 폴더만 `ftp:ftp` 소유자로 설정합니다.

기존 FTP가 포트를 쓰고 있으면 전환 시 중단합니다. 방화벽은 클라이언트에서 Worker InternalIP의
TCP **6380, 8076–8079**에 접근할 수 있도록 준비합니다. passive 전송 중에는 데이터 포트도 사용합니다.
namespace 정책에서 hostNetwork와 hostPath를 허용해야 합니다.

방화벽 요청은 **파일 전송 클라이언트의 허용 IP/CIDR → 선택한 각 FTP 노드 InternalIP**를 기준으로 합니다.

| 목적지 TCP 포트 | 용도 | 확인 |
| --- | --- | --- |
| `6380` | FTP 로그인·제어 연결 | 로그인 성공 |
| `8076–8079` | Passive 목록 조회·파일 전송 | 목록·업로드·다운로드 성공 |

APP VIP의 443과 별도로 각 Worker에 위 포트를 개방합니다. 호스트 방화벽과 중간 네트워크 방화벽 모두 확인합니다.
파일은 접속한 노드에만 저장되므로 Airflow·Portal이 읽을 위치도 함께 결정합니다.

## 4. 관리 호스트의 계정 파일 준비

서버의 저장소 루트에서 [credentials.env.example](credentials.env.example)을 수정해 계정 파일로 사용합니다.
`FTP_USER`, `FTP_PASS`는 빈칸이므로 실제 사용할 값으로 채웁니다.

```bash
export FTP_CREDENTIAL_FILE="$PWD/deploy/ftp/credentials.env.example"
chmod 600 "$FTP_CREDENTIAL_FILE"
vi "$FTP_CREDENTIAL_FILE"
```

`vi` 대신 서버에서 사용하는 편집기로 수정해도 됩니다. 실제 계정 값을 입력한 파일은 커밋하지 않습니다.
Git 밖에 복사해 사용하려면 복사본의 절대 경로를 `FTP_CREDENTIAL_FILE`로 지정하고 `chmod 600`을 적용합니다.
이미 사용 중인 계정 파일이 있으면 그 경로를 지정하고 재생성하지 않습니다. 새 Bash 세션에서도 같은 경로를 다시 export합니다.

계정 파일은 다음 규칙으로 작성합니다.

- `FTP_USER=값`, `FTP_PASS=값` 두 줄을 입력합니다. `export`나 값을 감싸는 따옴표는 넣지 않습니다.
- 사용자 이름에는 영문·숫자·밑줄·하이픈만 사용합니다.
- 비밀번호는 비워 두지 않으며 줄바꿈·역슬래시를 넣지 않습니다.

모든 대상 노드는 `etch-ftp/ftp-credentials` Secret을 공유합니다. 기본 계정은 없습니다.

## 5. 검사 후 배포

관리 호스트의 저장소 루트로 돌아옵니다. 앞서 export한 세 변수를 사용합니다.
실행기는 [env/prod.env](env/prod.env)을 자동으로 읽어 `FTP_IMAGE`의 사내 Docker Hub 미러 이미지를 적용합니다.
기존 공개 이미지 digest를 유지한 선언이며, 사내 미러의 해당 digest 제공 여부·접근·CA는 Worker에서 확인합니다.
다른 경로 또는 digest가 필요하면 이 env의 `FTP_IMAGE`를 실제 주소로 바꿉니다. `http://`, `https://`는 붙이지 않습니다.
registry 인증이 필요하면 `etch-ftp` namespace에 pull Secret을 미리 준비하고 같은 env의 `IMAGE_PULL_SECRET`에 이름을 입력합니다.
빈 값이면 pull Secret을 추가하지 않습니다. FTP 로그인용 계정 파일과 이미지 설정 env는 별개입니다.
별도 env는 `export FTP_ENV=/절대/경로/ftp.env`로 지정합니다. 별도 overlay 운영은 [수동 배포](03_KUBERNETES.md)를 사용합니다.

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check
# 위 검사가 통과하고 출력된 context·노드·IP가 맞으면 실행합니다.
make ftp-up
```

| 명령 | 처리 내용 |
| --- | --- |
| `ftp-check` | 이미지 설정·선택 pull Secret 존재, 계정 형식·권한, 원본 렌더, 대상 노드 상태, 기존 Secret 일치 여부 검사 |
| `ftp-up` | 같은 검사 → namespace 준비 → 없는 Secret 생성 → 노드 라벨 → 스택 적용 → 최대 5분 기동 대기 → Pod 위치 출력 |

기존 Secret이 입력과 다르면 변경 전에 중단합니다. 동일 입력으로 재실행할 수 있고 파일 데이터를 삭제하지 않습니다.
배포 중 실패하면 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 재실행합니다.

스크립트는 `deploy/ftp/scripts/up.py`이며 Python 표준 라이브러리만 사용합니다.
모든 클러스터 명령은 명시한 context를 사용합니다.

이 실행기는 `k8s/` 공통 원본에 운영 env의 이미지·pull Secret을 반영합니다.
`kubectl apply -k deploy/ftp/k8s`를 직접 실행하면 env가 적용되지 않고 공개 이미지를 사용합니다.
다른 저장 경로나 추가 패치가 필요하면 [수동 배포·overlay 절차](03_KUBERNETES.md)를 사용합니다.

검사 통과는 이미지 pull·원격 디스크·방화벽·실제 FTP 인증 성공을 보장하지 않습니다.

## 6. 완료 확인

[접속 확인과 운영](02_OPERATIONS.md)의 업로드·다운로드 검증까지 수행하면 설치가 완료됩니다.
각 Worker마다 Pod의 `NODE`, 실제 접속 IP, 업로드 후 호스트 파일 위치를 확인합니다.
다른 노드의 저장 폴더에 테스트 파일이 생기지 않는 것도 확인합니다.
현재 구성은 IPv4 직접 접속과 passive 모드용이며 Service·Ingress·VIP를 만들지 않습니다.
TLS나 NAT 주소를 자동 설정하지 않습니다.

검증 후에는 [서비스 기록](../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 대상 노드·접속 주소·확인일·결과를,
[네트워크 기록](../shared/docs/infrastructure/network.md#ftp-직접-접속)을 실제 방화벽 확인 결과와 함께 갱신합니다.
