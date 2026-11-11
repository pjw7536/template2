# Monitoring 설치

[앱 안내](../README.md) · 다음: [갱신·운영](02-operations.md)

고정 chart로 Monitoring을 설치합니다. 모든 명령은 관리 호스트(CP1 등)의 저장소 루트, 같은 Bash 세션에서 실행하며 각 Worker에서 반복하지 않습니다.
새 Bash 세션에서는 3단계의 `KUBE_CONTEXT`, `MONITORING_ENV`와, 다른 chart 경로를 쓰면 `MONITORING_CHART_FILE`을 다시 export합니다.

## 1. 준비물

| 위치 | 준비할 것 |
| --- | --- |
| 관리 호스트 | 저장소, Python 3.10+, Helm 3.19+, kubectl, 클러스터 접속용 kubeconfig |
| Kubernetes | 버전 1.25+와 Operator CRD·ClusterRole·Job 등을 설치할 권한 |
| 지정 Worker | Ready 상태, 차단 taint 없음, 데이터 디스크·여유 공간, 사내 미러 접근 |
| 웹 접속 경로 | 기본 HTTPS 접속을 사용하면 공용 Traefik·DNS/VIP·도메인 인증서 |

- 폴더 준비 Job은 root 권한과 `hostPath`, node-exporter는 `hostNetwork`와 `hostPath`를 사용하므로 namespace 정책에서 허용되어야 합니다.
- 기존 Prometheus Operator가 있는 클러스터는 기존 모니터링을 사용할 수 있는지 먼저 확인합니다. 배포 도구는 새 설치에서 기존 Operator CRD를 발견하면 중단합니다.

## 2. 고정 chart 준비

**목적:** `kube-prometheus-stack` **91.4.0** 패키지를 준비합니다. 버전과 SHA-256 `10d54f6984e5f97b2e96e64440c7c0c37af2ed1b17c1521fa6c0da3529bdeec1`은 [chart.lock.json](../helm/chart.lock.json)에 고정되어 있습니다.
**실행 위치:** 사내 미러에 접근할 수 있는 관리 호스트. 이미 파일이 있으면 생략합니다.

```bash
python3 deploy/monitoring/scripts/manage.py fetch-chart
```

**기대 결과:** chart lock의 `proxy-raw-github.com` 미러에서 받아 SHA-256을 검증한 `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz`가 생깁니다. chart 파일은 Git에 커밋하지 않습니다.

**실패 시:** 외부 PC에서 같은 버전의 [공식 release 파일](https://github.com/prometheus-community/helm-charts/releases/download/kube-prometheus-stack-91.4.0/kube-prometheus-stack-91.4.0.tgz)을 받아 관리 호스트의 같은 경로에 복사합니다. 다른 위치에 두었다면 경로를 지정합니다.

```bash
export MONITORING_CHART_FILE=/절대경로/kube-prometheus-stack-91.4.0.tgz
```

검사·배포는 파일의 SHA-256을 확인하며 chart를 자동 다운로드하지 않습니다. 의존 chart가 패키지에 포함되어 있으므로 `helm dependency update`를 실행하지 않습니다.

## 3. context와 env 설정

**목적:** 대상 클러스터와 데이터를 저장할 Worker를 정하고 env를 실제 값으로 맞춥니다.

```bash
kubectl config get-contexts
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
export MONITORING_ENV="${MONITORING_ENV:-$PWD/deploy/monitoring/env/k8s.env}"
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$KUBE_CONTEXT" get node "$(sed -n 's/^NODE_NAME=//p' "$MONITORING_ENV")" -o wide
chmod 600 "$MONITORING_ENV"
vi "$MONITORING_ENV"
```

Make 명령과 Python 명령은 export한 `MONITORING_ENV`를 사용합니다. 다른 env는 그 파일의 절대 경로를 export합니다.
현재 선언값은 [env/k8s.env](../env/k8s.env), 배치 대상 Worker의 확인 상태는 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)에서 확인합니다.

| 설정 | 무엇을 입력하나요? |
| --- | --- |
| `NODE_NAME` | 전체 스택을 실행할 Worker의 **kubernetes.io/hostname 값**. 위 조회에서 Ready 확인 |
| `DATA_HOST_PATH` | 해당 Worker의 전용 데이터 경로. 신규 설치 기본값 `/appdata/monitoring` |
| `DOCKER_REGISTRY`·`QUAY_REGISTRY`·`GHCR_REGISTRY`·`K8S_REGISTRY` | 사내 미러 경로. [이미지 미러 설정](#이미지-미러-설정) 확인 |
| `IMAGE_PULL_SECRET` | 미러 인증이 필요할 때 사용할 기존 Kubernetes Secret 이름. 인증이 없으면 빈 값 |
| `INGRESS_ENABLED` | `true`면 서비스별 도메인으로 HTTPS 접속, `false`면 port-forward 전용 |
| `GRAFANA_HOST`·`PROMETHEUS_HOST`·`ALERTMANAGER_HOST` | 서비스별 도메인. 서로 달라야 하며 port-forward 모드에서는 빈 값 |
| `NAMESPACE`·`GRAFANA_ADMIN_SECRET` | 기본값 `monitoring`, `monitoring-grafana-admin`. [5단계](#5-namespace와-관리자-secret-준비)에서 준비 |

이 문서의 명령은 기본 namespace와 Secret 이름을 사용합니다. 이름을 바꾸면 명령에서도 함께 바꿉니다.

### 저장소와 폴더 자동 생성

데이터는 `NODE_NAME` Worker의 `DATA_HOST_PATH` 아래에 저장합니다. 폴더는 배포 시 자동 생성되므로 수동으로 만들지 않지만, 데이터 디스크가 의도한 위치에 마운트되어 있고 여유 공간이 있는지는 먼저 확인합니다.
**새로 생성하는 서비스 폴더**에는 아래 소유권과 권한 `0770`을 적용합니다.

| 서비스 폴더 | 소유 UID:GID | local PV 예약 용량 |
| --- | --- | ---: |
| `prometheus` | `1000:2000` | 20Gi |
| `alertmanager` | `1000:2000` | 2Gi |
| `grafana` | `472:472` | 5Gi |

- local PV는 해당 노드의 폴더를 데이터 볼륨으로 연결하며 StorageClass가 필요하지 않습니다. 예약 용량은 실제 디스크 할당이나 사용량 제한이 아닙니다.
- Prometheus 보존 기준은 7일 또는 16GB, Alertmanager는 120h이며 WAL 등 추가 공간도 필요합니다.
- 기존 폴더·하위 데이터의 소유권과 권한은 보존합니다. 사용자 지정 UID/GID를 사용하면 폴더 권한도 직접 맞춥니다.
- 저장 경로가 일반 파일·심볼릭 링크이거나 기존 PV 폴더가 사라졌으면 중단하며 PV·Helm 배포로 넘어가지 않습니다.
- PV reclaim policy는 `Retain`이며 정상 갱신 시 PV·PVC·namespace를 삭제하지 않습니다. **지정 Worker 한 대에 저장하므로 고가용성 구성은 아닙니다.**

### 이미지 미러 설정

각 이미지가 실행될 노드에서 해당 미러에 접근할 수 있어야 합니다. registry 값은 URL scheme 없이 `레지스트리/proxy경로`로 입력하며 끝에 `/`를 붙이지 않습니다.
실제 주소의 관리 원본은 [사내 저장소·미러](../../shared/docs/infrastructure/repositories.md)입니다.

| env 키 | 외부 원본 | 사용하는 이미지 |
| --- | --- | --- |
| `DOCKER_REGISTRY` | docker.io | Grafana, 폴더 준비용 `library/busybox:1.37.0` |
| `QUAY_REGISTRY` | quay.io | Prometheus·Operator·Alertmanager·node-exporter·Grafana sidecar·config reloader |
| `GHCR_REGISTRY` | ghcr.io | webhook 인증서 초기화 이미지 |
| `K8S_REGISTRY` | registry.k8s.io | kube-state-metrics |

Docker Hub 미러 하나만으로는 모든 이미지를 받을 수 없습니다. [4단계](#4-원본실제-설정-검사)의 `images.txt` 전체를 확인하고, 미러에 없는 이미지·태그는 승인된 경로로 반입합니다.
`IMAGE_PULL_SECRET`에는 registry 인증 Secret의 **이름만** 입력합니다. Grafana 로그인용 Secret과는 별개입니다.

### 선택 설정

#### port-forward로만 접속하기

공용 HTTPS 경로를 사용하지 않을 때는 env를 아래처럼 바꿉니다. 6단계의 Traefik·인증서 준비는 생략하며, Grafana를 사용한다면 관리자 Secret은 여전히 필요합니다.

```dotenv
INGRESS_ENABLED=false
GRAFANA_HOST=
PROMETHEUS_HOST=
ALERTMANAGER_HOST=
```

설치 후 접속할 PC에서 같은 클러스터의 context를 지정해 실행합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-grafana 3000:80

# 다른 터미널에서 같은 context를 지정한 뒤 실행합니다.
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

주소는 `http://localhost:3000`, `http://localhost:9090/targets`입니다. 기본 HTTPS 모드에서는 Grafana가 공개 도메인으로 리다이렉트하므로 공용 주소로 확인합니다.

#### 일부 서비스를 끄거나 Helm 설정 추가하기

환경별 추가 설정은 비밀값 없는 values 파일로 작성합니다. Make 명령에는 추가 values 옵션이 없으므로 **검사·렌더·배포에 같은 파일**을 직접 전달합니다.

```bash
read -r -p '추가 values 파일 절대 경로: ' MONITORING_VALUES
python3 deploy/monitoring/scripts/manage.py check --env "$MONITORING_ENV" --values "$MONITORING_VALUES"
python3 deploy/monitoring/scripts/manage.py render --env "$MONITORING_ENV" \
  --values "$MONITORING_VALUES" --output deploy/monitoring/rendered
python3 deploy/monitoring/scripts/manage.py deploy --context "$KUBE_CONTEXT" \
  --env "$MONITORING_ENV" --values "$MONITORING_VALUES"
```

추가 values가 env와 기본 설정을 덮어쓸 수 있으므로 최종 리소스·이미지 목록을 확인한 뒤 배포합니다.
Prometheus를 끄려면 고정 chart가 Prometheus 전용 token Secret을 참조하지 않도록 관련 감시도 함께 끕니다.

```yaml
prometheus:
  enabled: false
kubernetesServiceMonitors:
  enabled: false
```

비활성 서비스는 폴더 준비·신규 PV·준비 대기 대상에서 제외합니다. 기존 PV·PVC는 삭제하지 않고, Grafana가 꺼져 있으면 관리자 Secret을, 모든 Ingress가 꺼져 있으면 Traefik controller·TLS를 조회하지 않습니다.

**기대 결과:** 실제 env·데이터 위치·이미지 미러·접속 방식을 정했습니다.

## 4. 원본·실제 설정 검사

**영향:** 이 단계는 클러스터를 변경하지 않습니다.

```bash
make server-check APP=monitoring PROFILE=prod
make monitoring-check
python3 deploy/monitoring/scripts/manage.py render \
  --env "$MONITORING_ENV" --output deploy/monitoring/rendered
cat deploy/monitoring/rendered/images.txt
```

| 명령·파일 | 확인하는 내용 |
| --- | --- |
| `server-check` | 저장소 기본 env와 chart의 정적 검사. 서버별 예제 값이 남아 있어도 통과할 수 있음 |
| `monitoring-check` | 선택한 `MONITORING_ENV`의 필수 값·형식과 Helm 렌더 검사 |
| `render` | 적용할 리소스를 파일로 생성. 설치는 하지 않음 |
| `images.txt` | 실행에 필요한 전체 이미지. Operator가 만드는 이미지와 폴더 준비용 BusyBox도 포함 |

**기대 결과:** 모든 명령이 통과하고 `images.txt`의 **모든 이미지·태그**를 각 실행 노드가 사내 미러에서 받을 수 있습니다. 렌더 성공만으로 실제 pull·디스크 권한·서버 보안 정책이 검증되지는 않습니다.
`rendered/monitoring.yaml`은 검토용이며 직접 `kubectl apply`하지 않습니다. CRD와 webhook 초기화 순서는 7단계의 배포 도구가 관리합니다.

## 5. Namespace와 관리자 Secret 준비

**목적:** 설치 영역(namespace)과 Grafana 로그인 계정 Secret을 준비합니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace monitoring --dry-run=client -o yaml \
  | kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n monitoring get secret monitoring-grafana-admin --ignore-not-found
```

`monitoring-grafana-admin`이 이미 있으면 기존 계정을 사용하고 아래 생성은 생략합니다. 처음 설치한다면 [관리자 env 샘플](../env/grafana-admin.env.example)을 Git 밖으로 복사해 편집합니다.

```bash
read -r -p 'Grafana 관리자 env 파일 절대 경로: ' GRAFANA_CREDENTIAL_FILE
(
  set -e
  umask 077
  if [ ! -e "$GRAFANA_CREDENTIAL_FILE" ]; then
    cp deploy/monitoring/env/grafana-admin.env.example "$GRAFANA_CREDENTIAL_FILE"
  fi
  vi "$GRAFANA_CREDENTIAL_FILE"
)
chmod 600 "$GRAFANA_CREDENTIAL_FILE"
```

`admin-user=`, `admin-password=` 두 키를 실제 계정으로 채우고 예시 비밀번호를 교체합니다. `export`나 값을 감싸는 따옴표는 넣지 않습니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n monitoring create secret generic monitoring-grafana-admin \
  --from-env-file="$GRAFANA_CREDENTIAL_FILE"
```

- 관리자 비밀번호는 Helm values나 Git에 넣지 않습니다.
- Grafana를 [선택 설정](#선택-설정)에서 비활성화했다면 namespace만 준비합니다.
- `IMAGE_PULL_SECRET`을 지정했다면 registry 인증용 Secret도 이 namespace에 미리 등록합니다.

## 6. HTTPS 웹 접속 준비

**목적:** 기본 HTTPS 모드에서 공용 Traefik에 서비스별 host 인증서를 등록합니다. port-forward 모드이거나 이미 등록되어 있으면 생략합니다.

| 화면 | 주소 |
| --- | --- |
| Grafana | `https://<GRAFANA_HOST>/` |
| Prometheus 수집 상태 | `https://<PROMETHEUS_HOST>/targets` |
| Alertmanager | `https://<ALERTMANAGER_HOST>/` |

실제 주소는 [서비스 접속 주소](../../shared/docs/infrastructure/services.md#서비스-접속-주소)에서 확인합니다. 접속 PC에서 이 도메인이 공용 진입점으로 연결되어야 하며, 하나의 SAN 인증서를 공유해도 세 host 모두 등록합니다.
처음 준비한다면 [공용 진입점 준비](../../shared/docs/README.md#https인증서)를 따른 뒤 실행합니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MONITORING_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MONITORING_TLS_KEY
for MONITORING_TLS_KEY_NAME in GRAFANA_HOST PROMETHEUS_HOST ALERTMANAGER_HOST; do
  MONITORING_TLS_HOST="$(sed -n "s/^${MONITORING_TLS_KEY_NAME}=//p" "$MONITORING_ENV")"
  make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$MONITORING_TLS_HOST" \
    TLS_CERT_FILE="$MONITORING_TLS_CERT" TLS_KEY_FILE="$MONITORING_TLS_KEY"
done
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

배포 도구는 인증서와 controller 변경 권한을 확인하고, 설치 후 기존 VIP·다른 앱·Traefik 배치를 보존하면서 Monitoring namespace의 라우팅 권한과 감시 범위만 추가합니다.

## 7. 배포

```bash
make monitoring-up
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods,pvc -o wide
```

배포 도구의 처리 순서는 다음과 같습니다.

1. 기존 Operator·chart 버전, 대상 노드, 관리자 Secret, HTTPS 설정을 확인합니다.
2. 지정 Worker에서 없는 저장 폴더를 생성하는 Job을 실행하고 완료를 기다립니다.
3. 데이터 볼륨을 연결하고 Helm으로 모니터링을 설치하거나 갱신합니다.
4. Helm `--wait`와 Operator가 만드는 Prometheus·Alertmanager StatefulSet의 준비를 기다리고 공용 웹 경로를 연결합니다.

준비 Job은 `Completed`가 정상이며 완료·실패 후 10분 뒤 자동 정리됩니다. 실패하면 [문제 해결](02-operations.md#문제-해결)을 따릅니다.

## 8. 완료 확인

**설치 완료는 화면과 실제 지표까지 확인한 상태입니다.**

| 확인할 곳 | 정상 기준 |
| --- | --- |
| `get pods,pvc` | 실행할 Pod가 Ready이고 데이터 PVC가 Bound |
| Grafana | 5단계의 관리자 계정으로 로그인. 기본 홈 [전체 서버 · 리소스 추세](02-operations.md#전체-서버-추세-대시보드)에 서버별 그래프와 상태 표가 표시됨 |
| Prometheus `/targets` | 수집 대상이 `UP`. `DOWN`인 대상은 endpoint·권한·통신 확인 |
| Alertmanager | 웹 화면과 현재 알림 설정 확인. 기본값은 외부 통지 없음 |

**다음 단계:** 실제 배치·접속 결과를 [서비스·앱 배치](../../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에 기록하고, 갱신·백업·장애 대응은 [운영 안내](02-operations.md)를 따릅니다.
