# 04. 앱 배포 준비

[가이드 홈](README.md) · 이전: [현황 확인](01-baseline.md) · 다음: [앱 배포](05-applications.md)

## 1. 저장소·배포 대상 — CP1

[선택 checkout](../../../SERVER_CHECKOUT.md)으로 필요한 앱을 준비합니다.
Keycloak만 사용하면 `keycloak`, Airflow도 사용하면 `keycloak-airflow`, 전체는 `all`을 선택합니다.
선택 명령은 기존 범위를 교체하며, 이미지 빌드 때만 `--with-source`를 추가합니다.

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

로컬 변경을 보존하고 의도한 커밋·context·노드인지 확인합니다.
앱별 `*-up`에는 `KUBE_CONTEXT`를 전달합니다. `make k8s-env`와 일부 Job 절차는 current-context를 사용하므로 실행 직전에 아래처럼 맞춥니다.

```bash
kubectl config use-context "$KUBE_CONTEXT"
kubectl config current-context
```

## 2. 앱별 준비물

| 앱 | 준비물·상세 안내 |
| --- | --- |
| [Keycloak](../../../keycloak/README.md) | 이미지, Worker의 DB 경로·권한, 80/443, env·TLS |
| [Airflow](../../../airflow/README.md) | 이미지·ODBC, DB/로그 경로, 고정 chart, env·TLS |
| [Portal](../../../portal/k8s/overlays/prod/README.md) | API/Web 이미지, 외부 DB, MinIO·업무 파일 저장소, env·TLS |
| [Monitoring](../../../monitoring/README.md) / [Headlamp](../../../headlamp/README.md) | 고정 chart·이미지·앱별 권한과 설정 |
| [FTP](../../../ftp/README.md) | 선택 Worker의 폴더·사용자 권한·직접 접속 포트 |

데이터 폴더는 실제 앱 실행 Worker에 준비합니다. PV 적용만으로 폴더·권한이 준비되지는 않습니다.
노드 런타임에서 이미지에 접근할 수 있는지도 확인합니다.

## 3. env·TLS·VIP

- [환경설정 규칙](../configuration/environment.md)에 따라 실제 env를 준비합니다. 기존 파일은 보존하고 권한은 600으로 관리합니다.
- 외부 env 파일은 앱 도구의 경로 인자로 지정합니다. env를 `source`로 실행하지 않습니다.
- 기존 DB에 연결할 때는 기존 credential과 맞춥니다. Keycloak 관리자·DB·사내 OIDC·Portal client 입력은 서로 다릅니다.
- [TLS 안내](../../../keycloak/TLS.md)로 도메인·SAN·만료·full chain·개인키를 확인하고 앱이 사용하는 namespace에 Secret을 준비합니다.
- [VIP 안내](../../ingress/VIP.md)로 LB backend·상태 검사·TLS 종료 위치와 Worker의 80/443 충돌을 확인합니다.

**완료 기준:** 선택한 앱의 이미지·chart·디스크·실제 env·TLS·배포 권한이 준비됩니다. 예시값이나 미정인 PVC 공급 방식이 남아 있으면 먼저 해결합니다.
