# 04. 앱 배포 전 공통 준비

[가이드 홈](README.md) · 이전: [클러스터 구축](03-cluster.md) · 다음: [앱 배포](05-applications.md)

기존 클러스터는 [환경 조회](01-baseline.md)를 마치고 여기서 시작합니다.
노드 Ready, 사용할 계정의 배포 권한, 앱별 이미지·저장소·네트워크 준비가 선행 조건입니다.

## 1. 저장소와 대상 선택 — CP1

[선택 checkout 안내](../../../SERVER_CHECKOUT.md)에 따라 저장소를 준비합니다.
Keycloak만 배포하면 `keycloak`, Keycloak과 Airflow는 `keycloak-airflow`, 여러 앱을 함께 관리하면 `all`을 선택합니다.
선택 명령은 기존 범위를 교체합니다. 이미지 빌드 때만 `--with-source`를 추가합니다.
이후 명령의 실행 디렉터리는 checkout 루트입니다.

```bash
pwd
git status --short
git branch --show-current
git rev-parse HEAD
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
```

앱별 `*-up`에는 `KUBE_CONTEXT`를 전달합니다. 기존 `make k8s-env`와 일부 Job 안내는
current-context를 사용하고 `KUBE_CONTEXT` 인자를 해석하지 않습니다. 해당 절차를 수행하기 직전에
아래 명령으로 로컬 kubeconfig의 선택을 바꾸고 대상을 다시 확인합니다. 이 명령은 클러스터를 배포하지 않습니다.

```bash
kubectl config use-context "$KUBE_CONTEXT"
kubectl config current-context
```

**완료 기준:** 의도한 커밋·context·노드 목록과 필요한 앱 파일이 확인됩니다.
로컬 변경이 있으면 내용을 먼저 확인하며 강제 초기화로 지우지 않습니다.

## 2. 이미지·차트·Worker 데이터

| 준비 | 상세 안내 | 완료 기준 |
| --- | --- | --- |
| Keycloak 이미지·DB 디렉터리·80/443 | [Keycloak](../../../keycloak/README.md) | 대상 Worker의 디스크·권한·이미지 접근 |
| Airflow 이미지·ODBC·DB·로그·고정 chart | [Airflow](../../../airflow/README.md) | env의 노드·경로와 실제 파일 일치, chart 검사 |
| Portal API/Web 이미지·외부 DB·파일 저장소 | [Portal overlay](../../../portal/k8s/overlays/prod/README.md) | placeholder 제거, migration도 같은 API 이미지, 필요한 PVC 공급 |
| Monitoring / Headlamp chart·이미지 | [Monitoring](../../../monitoring/README.md), [Headlamp](../../../headlamp/README.md) | 앱별 고정 chart·mirror·권한 준비 |
| FTP 폴더·직접 접속 포트 | [FTP](../../../ftp/README.md) | 선택 Worker의 경로·사용자 접근 준비 |

chart를 받았다고 컨테이너 이미지가 반입되지는 않습니다. 노드의 런타임이 실제 이미지를 가져올 수 있어야 합니다.
PV YAML을 적용해도 Worker 데이터 경로·권한이 자동으로 준비되지 않는 앱이 있습니다.
CP1 checkout을 백업하는 것과 Worker DB를 백업하는 것도 별개입니다.

## 3. 환경설정·인증서

[환경설정 규칙](../configuration/environment.md)에 따라 앱별 예시에서 실제 파일을 만듭니다.
기존 파일은 덮어쓰지 않습니다. Git 외부 경로나 앱에서 지원하는 Git 제외 경로 중 한 곳을 원본으로 정하고,
외부 파일은 해당 도구의 env 경로 인자로 지정합니다. 앱의 실제 입력 파일은 권한 600으로 관리합니다.

Keycloak의 관리자/DB credential, 사내 OIDC client, Portal client는 다른 입력입니다.
새 환경에서는 새 값을 준비하지만 기존 DB에 연결할 때는 기존 값을 맞춥니다.
env를 shell의 `source`로 실행하지 않고 프로젝트 검사 도구로 읽습니다.

TLS는 [인증서 안내](../../../keycloak/TLS.md)에서 도메인·SAN·만료·full chain·개인키 일치를 확인합니다.
각 앱이 참조하는 namespace에 올바른 TLS Secret이 있어야 합니다.
업무 도메인 인증서에 Keycloak 도메인도 포함된다고 가정하지 않습니다.

## 4. APP VIP 연결 준비

현재 값은 [현황](../infrastructure/cluster.md), 절차는 [VIP 안내](../../ingress/VIP.md)를 봅니다.
인프라 담당자는 backend와 상태 검사를 준비하고, Worker 담당자는 80/443 충돌과 이미지 접근을 확인합니다.
TLS는 현재 프로젝트의 목표 구성에서 Traefik이 종료합니다. 실제 LB 설정과 다른 경우 먼저 정합성을 맞춥니다.

**이 장의 완료 기준:** 사용할 앱의 실제 env·TLS·이미지·chart·디스크·권한이 준비됩니다.
필수값이 예시인 상태, PVC 공급 방식 미정, 이미지 접근 불가인 상태에서는 05장의 적용을 시작하지 않습니다.
