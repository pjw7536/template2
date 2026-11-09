# 앱 배포 준비와 검증

[공통 안내](../README.md)

- [배포 준비](#배포-준비)
- [앱 의존 관계](#앱-의존-관계)
- [접속·기능 검증](#접속기능-검증)

## 배포 준비


### 1. 저장소·배포 대상 — CP1

[선택 checkout](01-checkout.md#선택-checkout)으로 필요한 앱을 준비합니다.
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

### 2. 앱별 준비물

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

### 3. env·TLS·VIP

- [환경설정 규칙](../configuration/environment.md)에 따라 실제 env를 준비합니다. 기존 파일은 보존하고 권한은 600으로 관리합니다.
- 외부 env 파일은 앱 도구의 경로 인자로 지정합니다. env를 `source`로 실행하지 않습니다.
- 기존 DB에 연결할 때는 기존 credential과 맞춥니다. Keycloak 관리자·DB·사내 OIDC·Portal client 입력은 서로 다릅니다.
- [TLS 안내](../../../keycloak/docs/01-prepare.md#tlsca-준비)로 도메인·SAN·만료·full chain·개인키를 확인하고 앱이 사용하는 namespace에 Secret을 준비합니다.
- [VIP 안내](../ingress/setup.md)로 LB backend·상태 검사·TLS 종료 위치와 Worker의 80/443 충돌을 확인합니다.

**완료 기준:** 선택한 앱의 이미지·chart·디스크·env·TLS·배포 권한이 모두 준비되어야 합니다.
예시값이 남아 있거나 PVC에 저장소를 공급할 방법이 정해지지 않았다면 먼저 해결합니다.

## 앱 의존 관계


공통 준비를 마친 뒤 필요한 앱의 README에서 실제 설치 절차를 시작합니다.
이 문서는 의존 관계와 설치 완료 조건을 안내합니다. 실행 명령과 입력은 각 앱의 문서를 원본으로 사용합니다.

### 1. 공용 Traefik

앱보다 먼저 [Traefik 셋업](../ingress/setup.md)을 마칩니다.
공통 Ingress는 앱 env·앱 소스 없이 준비할 수 있습니다.
[APP VIP](../ingress/setup.md)의 Worker backend·인증서와 실제 HTTPS 연결을 확인합니다.
공용 Ingress 준비만으로 앱·DB·앱 Secret이 설치되지는 않습니다.

### 2. Keycloak

[Keycloak 설치 순서](../../../keycloak/README.md)를 따라 서버 배포 → 자체 설정 → 사내 로그인을 확인합니다.
Portal·Headlamp·기본 Airflow SSO는 이 준비를 마친 뒤 각 앱의 client를 연결합니다.
**완료 기준:** DB·Keycloak 정상, 사내 로그인과 사용자 필드 확인. client 등록만으로 사내 로그인 검증을 대신하지 않습니다.

### 3. Airflow

[Airflow 설치 순서](../../../airflow/README.md)에 따라 env·chart·이미지·ODBC·DB/로그 디스크와 기본 Keycloak 로그인을 준비합니다.
`NODE_NAME`은 실제 Worker의 자원·디스크·ODBC 접근과 다른 앱 배치 조건을 확인해 선택합니다.
최초 설치는 새 DB·계정을 준비하고 재배포는 기존 DB 비밀번호·Fernet 키를 보존합니다.
**완료 기준:** DB·scheduler health, UI 로그인. Portal 연동을 사용하면 토큰·API·시험 DAG 결과까지 확인합니다.
신규 DAG는 필요한 것만 검증 후 활성화합니다.

### 4. 운영 도구

| 앱 | 의존 관계와 설치 안내 | 완료 기준 |
| --- | --- | --- |
| [MinIO](../../../minio/README.md) | 공용 Traefik·저장소·이미지·계정. 다른 제품 앱 없이 설치 가능 | PVC Bound·초기화 Job Complete·콘솔·시험 파일 송수신 |
| [Monitoring](../../../monitoring/README.md) | chart·저장소·Grafana 계정. 기본 HTTPS에는 공용 Traefik 필요 | Grafana 로그인·노드 지표·Prometheus target |
| [Headlamp](../../../headlamp/README.md) | Keycloak·TLS/CA·client·관리자 그룹과 모든 API server의 OIDC 인증 | 관리자 접근 허용·별도 권한 없는 비관리자 거부 |
| [FTP](../../../ftp/README.md) | 선택 노드·폴더·포트·계정 파일. 노드 IP로 직접 접속 | passive 접속·파일 송수신·저장 노드 확인 |

MinIO는 Portal이 파일 기능을 사용하기 전에 준비합니다. Monitoring·FTP는 Keycloak 없이 설치할 수 있습니다.
Monitoring의 port-forward는 기본 HTTPS를 사용하지 않는 선택 설정입니다.
Headlamp는 Pod Ready와 client 등록 외에 API server 인증과 사용자 권한 검증까지 필요합니다.

### 5. Portal — 나중에 추가

`platform`으로 기반 앱을 운영했다면 [선택 checkout](01-checkout.md#선택-checkout)을 `all`로 확장합니다.
선택은 이전 범위를 교체하므로 `portal`만 선택해 기존 앱 파일을 제외하지 않습니다.

[Portal 설치 순서](../../../portal/README.md)를 따릅니다.
외부 PostgreSQL·extension, Keycloak, 공용 MinIO·파일 저장소, API/Web·migration 이미지를 먼저 준비합니다.
client 등록 → namespace·Secret·TLS → migration → 앱 → 공용 Traefik 연결 순서는 [배포 절차](../../../portal/docs/01-install.md#migration배포검증)를 확인합니다.
현재 `make portal-up`은 없으며 안내된 적용 명령을 사용합니다.

**완료 기준:** migration 사후 검사·API health·로그인/callback/logout·파일 업로드/다운로드 확인.
보존할 업무 파일은 `emptyDir` 대신 실제 PVC 등에 연결하고 참고·원본 데이터는 readOnly로 마운트합니다.

공유 클러스터에서는 각 앱의 배포 도구를 사용합니다.
Keycloak 정적 YAML을 직접 적용하면 공용 Traefik의 namespace 감시와 VIP 배치가 기본값으로 돌아갈 수 있습니다.

## 접속·기능 검증


클러스터 상태 → Worker 직접 접속 → VIP → DNS → 실제 기능 순서로 확인합니다.
배포하지 않은 앱은 `미배포`로 기록합니다.

### 1. 리소스 확인 — CP1

[배포 준비](#배포-준비)에서 `KUBE_CONTEXT`를 지정한 같은 터미널에서 실행합니다.

```bash
read -r -p '확인할 앱 namespace: ' APP_NAMESPACE
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get deployment,statefulset,daemonset
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get jobs,pvc
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get service,ingress,endpointslices
```

다음 상태를 모두 확인합니다.

- 필요한 replica 수가 준비되고 Pod의 READY가 충족됩니다.
- PVC는 Bound, 일회성 Job은 Completed 상태입니다.
- Service에 준비된 endpoint가 있습니다.

Pod가 Running이라는 이유만으로 앱이 준비됐다고 판단하지 않습니다.

### 2. HTTPS 확인 — 접근 가능한 PC

APP VIP를 사용하는 앱의 정상 health 경로로 확인합니다.
Portal은 `/api/v1/health/`, Airflow는 `/airflow/health`입니다.

```bash
read -r -p '앱 인증서 도메인: ' APP_HOST
read -r -p 'health 경로(/로 시작): ' APP_HEALTH_PATH
read -r -p '확인할 Worker 또는 VIP IP: ' TARGET_IP
read -r -p '신뢰할 CA PEM 파일 절대 경로: ' CA_FILE
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" --resolve "$APP_HOST:443:$TARGET_IP" \
  "https://$APP_HOST$APP_HEALTH_PATH"
```

같은 도메인·경로로 `TARGET_IP`를 각 backend → APP VIP 순서로 바꿔 실행합니다.
마지막에는 DNS도 확인합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" "https://$APP_HOST$APP_HEALTH_PATH"
```

OS가 해당 CA를 신뢰하면 `--cacert`를 생략할 수 있습니다.
인증서 검증을 건너뛰는 `-k`는 사용하지 않습니다.

**성공 기준:** TLS 검증을 통과하고 health 응답 내용이 정상이어야 합니다.
Airflow는 HTTP 200 외에 DB와 scheduler가 healthy인지도 확인합니다.
Keycloak은 [VIP 문서](../ingress/setup.md)의 도메인 검사와 아래 로그인 검증을 수행합니다.

### 3. 실제 기능 확인

| 앱 | 시나리오 |
| --- | --- |
| Keycloak | HTTPS → 사내 OIDC 로그인 → realm·사용자 claim |
| Portal | 로그인 callback → API → 로그아웃, 시험 파일 업로드·다운로드 |
| Airflow | UI 로그인·health, Portal 연동 시 시험 DAG 트리거·결과 |
| Monitoring / Headlamp | Grafana 지표·target / Keycloak 로그인·그룹별 리소스 조회 |
| FTP | 노드 passive 접속·시험 파일 송수신·저장 위치 |

시험 데이터는 정상 삭제 절차로 정리합니다.
결과에는 수행일·담당자, context·namespace, 커밋·이미지·chart 버전을 남깁니다.
정적 검사, 리소스 상태, 접속·기능 검증의 결과를 나누어 적고 미완료 항목과 다음 조치를 덧붙입니다.
비밀값은 기록하지 않습니다. 접근하지 못했거나 확인 대기 중인 항목은 성공으로 표시하지 않습니다.
