# 04. 앱 배포 준비

[가이드 홈](README.md) · 이전: [현황 확인](01-baseline.md) · 다음: [앱 배포](05-applications.md)

## 1. 저장소·배포 대상 — CP1

[선택 checkout](../../../SERVER_CHECKOUT.md)으로 필요한 앱을 준비합니다.
Portal 외 서비스를 먼저 운영하려면 `platform`, Portal까지 함께 운영하려면 `all`을 선택합니다.
Keycloak만 사용하면 `keycloak`, Keycloak·Airflow만 사용하면 `keycloak-airflow`를 선택할 수 있습니다.
선택 명령은 기존 범위를 교체하며, 이미지 빌드 때만 `--with-source`를 추가합니다.
서버에는 `deploy`와 루트 실행 파일만 받으며 공통 운영 문서는 `deploy/shared/docs`에 포함됩니다.
Portal을 추가할 때는 `platform`에서 `all`로 확장해 기존 서비스 파일을 유지합니다.

checkout 루트에서 실행합니다.

```bash
git status --short
git branch --show-current
git rev-parse HEAD
kubectl config get-contexts
read -r -p '배포할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
```

기존 변경 파일을 보존한 뒤, 배포할 커밋·context·노드가 맞는지 확인합니다.

공용 Ingress·앱별 배포와 서버 Secret 등록에는 `KUBE_CONTEXT`를 전달합니다.
명령이 현재 context를 암묵적으로 선택하도록 두지 않습니다.

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
# Portal을 나중에 추가할 때 해당 namespace를 준비한 뒤 등록하는 예입니다.
# make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
```

## 2. 앱별 준비물

| 앱 | 준비물·상세 안내 |
| --- | --- |
| [Keycloak](../../../keycloak/README.md) | 이미지, Worker의 DB 경로·권한, 80/443, env·TLS |
| [Airflow](../../../airflow/README.md) | 이미지·ODBC, DB/로그 경로, 고정 chart, env·TLS |
| [Portal](../../../portal/k8s/overlays/prod/README.md) | API/Web 이미지, 외부 DB, MinIO·업무 파일 저장소, env·TLS |
| [Monitoring](../../../monitoring/README.md) / [Headlamp](../../../headlamp/README.md) | 고정 chart·이미지·앱별 권한과 설정 |
| [FTP](../../../ftp/README.md) | 선택 Worker의 폴더·사용자 권한·직접 접속 포트 |

데이터 폴더는 앱이 실행될 Worker에 직접 준비합니다.
PV를 적용하는 것만으로 폴더가 생기거나 쓰기 권한이 설정되지는 않습니다.
같은 Worker의 컨테이너 런타임에서 이미지를 가져올 수 있는지도 확인합니다.

## 3. env·TLS·VIP

- [환경설정 규칙](../configuration/environment.md)에 따라 실제 env를 준비합니다. 기존 파일은 보존하고 권한은 600으로 관리합니다.
- 외부 env 파일은 앱 도구의 경로 인자로 지정합니다. env를 `source`로 실행하지 않습니다.
- 기존 DB에 연결할 때는 기존 credential과 맞춥니다. Keycloak 관리자·DB·사내 OIDC·Portal client 입력은 서로 다릅니다.
- [TLS 안내](../../../keycloak/03_TLS.md)로 도메인·SAN·만료·full chain·개인키를 확인하고 앱이 사용하는 namespace에 Secret을 준비합니다.
- [VIP 안내](../../ingress/VIP.md)로 LB backend·상태 검사·TLS 종료 위치와 Worker의 80/443 충돌을 확인합니다.

**완료 기준:** 선택한 앱의 이미지·chart·디스크·env·TLS·배포 권한이 모두 준비되어야 합니다.
예시값이 남아 있거나 PVC에 저장소를 공급할 방법이 정해지지 않았다면 먼저 해결합니다.
