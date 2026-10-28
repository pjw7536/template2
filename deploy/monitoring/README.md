# Kubernetes Monitoring

[배포 문서 안내](../README.md) · [Kubernetes 입문 가이드](../shared/docs/kubernetes/README.md)

새 Kubernetes 환경에는 기존 Compose Monitoring 대신 `kube-prometheus-stack`을 설치합니다.
Prometheus·Grafana·Alertmanager·kube-state-metrics·node-exporter와 Kubernetes 대시보드를 함께 설치합니다.
Portal·Keycloak·Airflow의 기동 여부와 관계없이 설치할 수 있습니다. 기존 지표 DB는 복원하지 않습니다.

## 배포 범위와 준비

- 고정 chart: `helm/chart.lock.json`. 의존 chart를 포함하며 서버에서 dependency update하지 않습니다.
- Python 3.10+, Helm 3.19+, kubectl, Kubernetes 1.25+가 필요합니다.
- 클러스터에 기존 Prometheus Operator가 있으면 먼저 기존 도구를 사용합니다. 배포 도구는 새 release 설치 시 기존 CRD를 발견하면 중단합니다.
- Operator CRD·ClusterRole 설치 권한이 필요합니다. node-exporter는 노드별 hostNetwork·hostPath를 사용하므로 namespace 정책에서 허용되어야 합니다.
- 선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh monitoring`입니다. `deploy/monitoring`, `deploy/shared`, 루트 Makefile만으로 실행합니다.
- 기본 접속은 공용 Traefik의 HTTPS 하위 경로입니다. Grafana는 `/grafana/`, Prometheus는 `/prometheus/`, Alertmanager는 `/alertmanager/`를 사용합니다.
- 공개 host·TLS Secret은 env로 지정합니다. 기존 Grafana 관리자 로그인을 유지하며 SSO·외부 알림 전송은 이 설정에서 추가하지 않습니다.
- 노드·Pod·kubelet/cAdvisor·API server·CoreDNS 지표를 수집합니다. etcd·scheduler·controller-manager·kube-proxy는 endpoint·인증이 미확정이라 제외합니다.
- 애플리케이션의 업무 지표·로그 수집·FTP 업로드 성공 여부는 기본 수집 범위에 포함되지 않습니다.

## 1. 서버 설정과 디스크 준비

공통 `manage.py`의 check/render/deploy는 `--values /경로/values.yaml`로 환경별 Helm 설정을 추가할 수 있습니다.
이 values 파일에는 비밀값을 넣지 않습니다.
검사와 배포에는 같은 override를 전달합니다. 최종 렌더에서 비활성화한 Grafana·Prometheus·Alertmanager는
준비 대기와 신규 local PV 생성 대상에서 제외합니다. 기존 PV·PVC는 도구가 삭제하지 않습니다.
Grafana가 비활성화돼 있으면 관리자 Secret도 조회하지 않습니다.

Prometheus를 끌 때는 고정 chart의 ServiceMonitor 인증 입력도 함께 맞춥니다.
Prometheus 전용 token Secret을 사용하는 기본 감시를 함께 끄는 override 예시입니다.

```yaml
prometheus:
  enabled: false
kubernetesServiceMonitors:
  enabled: false
```

로컬 개발은 별도 wrapper와 `local/monitoring`의 values를 사용합니다.
기본 서버 검사·배포는 local 파일을 읽지 않습니다.

```bash
# Git으로 받은 일반 설정을 확인합니다.
chmod 600 deploy/monitoring/env/k8s.env
```

파일을 편집합니다. `NODE_NAME`은 Ready 상태이며 차단 taint가 없는 Worker의 hostname label입니다.
`DATA_HOST_PATH`는 해당 노드의 전용 경로입니다. 기존 업무 데이터 경로를 지정하지 않습니다.

네 registry 설정에는 사내 미러의 upstream별 proxy 경로를 입력합니다. URL scheme 없이
`사내레지스트리/proxy경로` 형식이며 실제 주소는 코드에 고정하지 않습니다.

| 변수 | 원본 registry |
| --- | --- |
| `DOCKER_REGISTRY` | docker.io — Grafana |
| `QUAY_REGISTRY` | quay.io — Prometheus·Operator·Alertmanager·node-exporter·sidecar |
| `GHCR_REGISTRY` | ghcr.io — webhook 인증서 초기화 이미지 |
| `K8S_REGISTRY` | registry.k8s.io — kube-state-metrics |

Docker Hub 미러만으로는 충분하지 않습니다. 아래 렌더 결과의 `images.txt`에 나오는 **모든 태그**가
사내 미러에서 pull 가능한지 확인합니다. 미러에 없으면 승인된 경로에 동일 이미지를 반입합니다.
인증이 필요하면 `IMAGE_PULL_SECRET`에 동일 namespace의 registry Secret 이름을 입력합니다.

저장소의 운영 접속 기본값은 다음과 같습니다. 인증서에는 `etch.samsungds.net`이 포함되어야 합니다.

```dotenv
INGRESS_ENABLED=true
INGRESS_HOST=etch.samsungds.net
INGRESS_TLS_SECRET=monitoring-tls
```

공용 Traefik은 [공용 진입점 준비](../shared/ingress/README.md)에 따라 먼저 기동합니다.
`monitoring-up`은 기존 VIP·배치를 보존하고 Monitoring namespace의 라우팅 권한과 감시만 추가합니다.
최종 Helm override에서 모든 Ingress를 끄면 controller·TLS를 조회하지 않습니다.
port-forward 전용 환경은 `INGRESS_ENABLED=false`, `INGRESS_HOST=`, `INGRESS_TLS_SECRET=`로 설정합니다.

선택한 Worker에서 예시 경로의 디렉터리를 준비합니다. `DATA_HOST_PATH`를 바꿨다면 함께 바꿉니다.

```bash
sudo install -d -o 1000 -g 2000 -m 0770 /srv/monitoring/prometheus /srv/monitoring/alertmanager
sudo install -d -o 472 -g 472 -m 0770 /srv/monitoring/grafana
```

local PV로 다음 용량을 예약합니다. StorageClass는 필요하지 않습니다.

| 서비스 | 예약 용량 |
| --- | ---: |
| Prometheus | 20Gi |
| Alertmanager | 2Gi |
| Grafana | 5Gi |

예약 용량이 파일시스템 사용량을 제한하는 것은 아니므로 실제 디스크 여유 공간을 확인합니다.
Prometheus 보존 기준은 7일 또는 16GB이며 WAL 등 추가 공간이 필요합니다.

서버 한 대에 데이터를 보관하므로 고가용성 구성은 아닙니다.
Pod 재시작에도 데이터를 보존하며 PV reclaim policy는 Retain입니다. PVC·namespace는 정상 업데이트 시 삭제하지 않습니다.

## 2. 고정 chart 준비

외부 연결이 가능한 PC에서 다운로드하거나 서버에서 URL에 접근 가능하면 직접 실행합니다.

```bash
python3 deploy/monitoring/scripts/manage.py fetch-chart
```

외부 접속이 불가능하면 생성된 `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz`를
서버의 같은 경로에 복사합니다. 별도 경로는 `MONITORING_CHART_FILE=/절대경로/chart.tgz`로 지정합니다.
도구는 lock의 SHA-256을 검증합니다. chart는 저장소에 커밋하지 않으며 검사·배포 시 자동 다운로드하지 않습니다.

## 3. 원본·실제 설정 검사

```bash
# 공개 예시로 검사하며 클러스터를 변경하지 않습니다.
make server-check APP=monitoring

# 실제 서버 설정과 미러 이미지 치환 검사
make monitoring-check
python3 deploy/monitoring/scripts/manage.py render \
  --env deploy/monitoring/env/k8s.env --output deploy/monitoring/rendered
cat deploy/monitoring/rendered/images.txt
```

`monitoring.yaml`은 검토용이며 직접 apply하지 않습니다. 실제 설치는 Helm이 CRD와 webhook hook 순서를 관리합니다.
렌더는 파일 형식·chart·미러 치환을 검사하지만 실제 image pull·디스크 권한·클러스터 정책은 확인하지 않습니다.

## 4. Namespace와 관리자 Secret 준비

Grafana를 비활성화했다면 namespace를 준비한 뒤 아래 관리자 Secret 등록 블록은 생략합니다.

```bash
read -r -p '대상 Kubernetes context: ' MONITORING_CONTEXT
kubectl --context "$MONITORING_CONTEXT" create namespace monitoring --dry-run=client -o yaml \
  | kubectl --context "$MONITORING_CONTEXT" apply -f -

# 접근 권한 600인 외부 파일에 admin-user=계정, admin-password=비밀번호를 작성합니다.
read -r -p 'Grafana 관리자 env 파일 절대 경로: ' GRAFANA_CREDENTIAL_FILE
kubectl --context "$MONITORING_CONTEXT" -n monitoring create secret generic monitoring-grafana-admin \
  --from-env-file="$GRAFANA_CREDENTIAL_FILE"
```

`NAMESPACE`·`GRAFANA_ADMIN_SECRET`을 변경했다면 명령의 이름도 맞춥니다.
Secret이 이미 있으면 생성 단계를 생략하며 임의로 덮어쓰지 않습니다.
관리자 비밀번호는 Helm values나 저장소에 넣지 않습니다.

Grafana DB가 생성된 후에는 Secret만 변경해도 기존 비밀번호가 바뀌지 않습니다. 계정 갱신은 Grafana에서 수행합니다.
registry 인증용 Secret도 이 단계에 준비합니다.

Ingress를 사용하면 같은 namespace에 업무 도메인의 TLS Secret도 준비합니다.
기존 `headlamp-tls`와 같은 도메인의 인증서를 사용하되 Secret은 namespace마다 별도로 등록·갱신합니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MONITORING_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MONITORING_TLS_KEY
kubectl --context "$MONITORING_CONTEXT" -n monitoring create secret tls monitoring-tls \
  --cert="$MONITORING_TLS_CERT" --key="$MONITORING_TLS_KEY"
```

Secret이 이미 있으면 생성 단계를 생략합니다. `NAMESPACE`·`INGRESS_TLS_SECRET`을 변경했다면 위 명령도 맞춥니다.
배포는 최종 렌더의 TLS Secret과 공용 controller 변경 권한을 확인한 뒤 PV·Helm 변경을 시작합니다.

## 5. 배포와 확인

```bash
make monitoring-up KUBE_CONTEXT="$MONITORING_CONTEXT"
kubectl --context "$MONITORING_CONTEXT" -n monitoring get pods,pvc
```

`https://etch.samsungds.net/grafana/`에서 관리자 계정으로 로그인합니다.
Kubernetes / Compute Resources / Cluster·Node·Pod 대시보드에서 데이터가 들어오는지 확인합니다.
`https://etch.samsungds.net/prometheus/targets`에서 수집 대상이 `UP`인지 확인하고,
`https://etch.samsungds.net/alertmanager/`에서 화면과 알림 설정을 확인합니다.
Ingress host가 다르면 위 주소도 같은 host로 바꿉니다.

port-forward 전용 설정에서는 다음 명령으로 접속할 수 있습니다.

```bash
kubectl --context "$MONITORING_CONTEXT" -n monitoring port-forward svc/monitoring-grafana 3000:80
# 다른 터미널에서 실행합니다.
kubectl --context "$MONITORING_CONTEXT" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

이 모드의 주소는 `http://localhost:3000`과 `http://localhost:9090/targets`입니다.
운영 하위 경로 모드에서는 Grafana가 공개 HTTPS 주소로 리다이렉트하므로 공용 주소로 확인합니다.

기존 node-exporter가 host port 9100을 사용하면 새 DaemonSet과 충돌합니다.
이전 exporter를 정리하거나 기존 공용 Monitoring을 사용합니다.

기본 구성의 Alertmanager는 수신자를 null로 두며 외부 메시지를 보내지 않습니다.
최종 렌더의 일반 workload 준비는 Helm `--wait`로 확인합니다.
활성 Prometheus·Alertmanager만 실제 CR 이름에 대응하는 StatefulSet의 생성과 준비를 추가로 기다립니다.

## 갱신·운영

- 같은 chart의 설정 재적용은 동일 명령을 사용합니다. `MONITORING_ENV=/절대경로/k8s.env`로 외부 설정을 받을 수 있습니다.
- chart 버전이 다른 기존 release에는 도구가 배포하지 않습니다. 버전 변경은 CRD 호환성·공식 upgrade 문서를 검토한 뒤 별도로 진행합니다.
- 실패 시 DB·namespace를 자동 삭제하지 않습니다. 첫 설치가 일부만 완료되면 Helm release 상태와 CRD를 확인하며 CRD를 임의 삭제하지 않습니다.
- Grafana DB·대시보드와 지표를 백업할 때는 별도 디스크에 보관합니다. 같은 노드의 데이터만으로 노드 장애를 복구할 수 없습니다.
- `make env-check APP=monitoring`과 `make monitoring-check`는 Kubernetes 입력·렌더를 검사합니다.

하위 경로 참고: [Grafana 프록시 설정](https://grafana.com/tutorials/run-grafana-behind-a-proxy/),
[Prometheus external URL·route prefix](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/).

공식 근거: [kube-prometheus-stack 설치·CRD·업데이트](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-91.4.0/charts/kube-prometheus-stack).
