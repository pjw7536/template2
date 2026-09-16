# Kubernetes Monitoring

[배포 문서 안내](../README.md)

기존 Compose Monitoring은 신규 Kubernetes 환경에서 **kube-prometheus-stack**으로 대체합니다.
Prometheus·Grafana·Alertmanager·kube-state-metrics·node-exporter와 Kubernetes 대시보드를 함께 설치합니다.
Portal·Keycloak·Airflow의 기동 여부와 관계없이 설치할 수 있습니다. 기존 지표 DB는 복원하지 않습니다.

## 배포 범위와 준비

- 고정 chart: `helm/chart.lock.json`. 의존 chart를 포함하며 서버에서 dependency update하지 않습니다.
- Python 3.10+, Helm 3.19+, kubectl, Kubernetes 1.25+가 필요합니다.
- 클러스터에 기존 Prometheus Operator가 있으면 먼저 기존 도구를 사용합니다. 배포 도구는 새 release 설치 시 기존 CRD를 발견하면 중단합니다.
- Operator CRD·ClusterRole 설치 권한이 필요합니다. node-exporter는 노드별 hostNetwork·hostPath를 사용하므로 namespace 정책에서 허용되어야 합니다.
- 선택 checkout은 `bash deploy/shared/scripts/checkout-server.sh monitoring`입니다. `deploy/monitoring`, `deploy/shared`, 루트 Makefile만으로 실행합니다.
- 기본 접속은 **localhost port-forward**입니다. 공개 DNS·Ingress·SSO·외부 알림 전송은 설정하지 않습니다.
- 노드·Pod·kubelet/cAdvisor·API server·CoreDNS 지표를 수집합니다. etcd·scheduler·controller-manager·kube-proxy는 endpoint·인증이 미확정이라 제외합니다.
- 애플리케이션의 업무 지표·로그 수집·FTP 업로드 성공 여부는 기본 수집 범위에 포함되지 않습니다.

## 1. 서버 설정과 디스크 준비

공통 `manage.py`의 check/render/deploy는 `--values /경로/values.yaml`로 환경별 비밀값 없는
Helm override를 받을 수 있습니다. 로컬 개발은 별도 wrapper와 `local/monitoring`의 values를 사용합니다.
기본 서버 검사·배포는 local 파일을 읽지 않습니다.

```bash
cp deploy/monitoring/env/k8s.env.example deploy/monitoring/env/k8s.env
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

선택한 Worker에서 예시 경로의 디렉터리를 준비합니다. `DATA_HOST_PATH`를 바꿨다면 함께 바꿉니다.

```bash
sudo install -d -o 1000 -g 2000 -m 0770 /srv/monitoring/prometheus /srv/monitoring/alertmanager
sudo install -d -o 472 -g 472 -m 0770 /srv/monitoring/grafana
```

local PV로 Prometheus 20Gi·Alertmanager 2Gi·Grafana 5Gi를 예약합니다. StorageClass는 필요하지 않습니다.
이는 파일시스템 quota가 아니므로 실제 디스크 여유 공간을 확인합니다. Prometheus 보존은 7일 또는 16GB이며
WAL 등 추가 공간이 필요합니다. 서버 한 대에 데이터를 보관하므로 고가용성 구성은 아닙니다.
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
Secret이 이미 있으면 생성 단계를 생략하며 임의로 덮어쓰지 않습니다. 관리자 비밀번호는
Helm values나 저장소에 넣지 않습니다. Grafana DB가 생성된 후 Secret만 변경해도 기존 비밀번호는 바뀌지 않으므로
계정 갱신은 Grafana에서 수행합니다. registry 인증용 Secret도 이 단계에 준비합니다.

## 5. 배포와 확인

```bash
make monitoring-up KUBE_CONTEXT="$MONITORING_CONTEXT"
kubectl --context "$MONITORING_CONTEXT" -n monitoring get pods,pvc
kubectl --context "$MONITORING_CONTEXT" -n monitoring port-forward svc/monitoring-grafana 3000:80
```

명령을 실행한 컴퓨터의 `http://localhost:3000`에 접속합니다. 서버에서 실행했다면 SSH 터널을 사용합니다.
Grafana의 Kubernetes / Compute Resources / Cluster·Node·Pod 대시보드에서 데이터가 들어오는지 확인합니다.
Prometheus Targets는 다음 port-forward로 확인할 수 있습니다.

```bash
kubectl --context "$MONITORING_CONTEXT" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

`http://localhost:9090/targets`에서 기본 수집 대상의 UP 상태를 확인합니다. 기존 node-exporter가 host port 9100을
사용한다면 새 DaemonSet과 충돌하므로 이전 exporter를 정리하거나 기존 공용 Monitoring을 사용합니다.
Alertmanager는 배포하지만 수신자는 null로 두며 외부 메시지를 보내지 않습니다.

## 갱신·운영

- 같은 chart의 설정 재적용은 동일 명령을 사용합니다. `MONITORING_ENV=/절대경로/k8s.env`로 외부 설정을 받을 수 있습니다.
- chart 버전이 다른 기존 release에는 도구가 배포하지 않습니다. 버전 변경은 CRD 호환성·공식 upgrade 문서를 검토한 뒤 별도로 진행합니다.
- 실패 시 DB·namespace를 자동 삭제하지 않습니다. 첫 설치가 일부만 완료되면 Helm release 상태와 CRD를 확인하며 CRD를 임의 삭제하지 않습니다.
- Grafana DB·대시보드와 지표를 백업할 때는 별도 디스크에 보관합니다. 같은 노드의 데이터만으로 노드 장애를 복구할 수 없습니다.
- `make env-check APP=monitoring`과 `make monitoring-check`는 Kubernetes 입력·렌더를 검사합니다.

공식 근거: [kube-prometheus-stack 설치·CRD·업데이트](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-91.4.0/charts/kube-prometheus-stack).
