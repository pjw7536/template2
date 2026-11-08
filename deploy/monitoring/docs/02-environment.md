# Monitoring 환경설정과 선택 설정

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

[서버·chart 준비](01-setup.md)를 마친 뒤 읽습니다. **실행 위치:** 관리 호스트의 저장소 루트, 같은 Bash 터미널입니다. 새 터미널에서는 아래 context와 env 선택을 다시 수행합니다.

## 1. 서버 설정과 디스크 준비

**이후 명령은 관리 서버의 저장소 루트, 같은 Bash 세션에서 실행합니다.**
먼저 접속할 클러스터와 모니터링 데이터를 저장할 Worker를 확인합니다.

[현재 서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)의 `khinfow01`은
클러스터 Worker 추가가 사용자 확인된 Airflow·Monitoring 배포 대상입니다.
Ready·실제 Monitoring 배포·지표 수집 상태는 아래 조회와 배포 후 확인 단계에서 별도로 확인합니다.

```bash
kubectl config get-contexts
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$KUBE_CONTEXT" get node khinfow01 -o wide

export MONITORING_ENV="$PWD/deploy/monitoring/env/k8s.env"
chmod 600 "$MONITORING_ENV"
vi "$MONITORING_ENV"
```

`vi`는 사용하는 편집기로 바꿔도 됩니다. 설정 파일은 [env/k8s.env](../env/k8s.env)입니다.

| 설정 | 무엇을 입력하나요? |
| --- | --- |
| `NODE_NAME` | 기본값 `khinfow01`. Worker 추가는 사용자 확인. 위 조회의 **kubernetes.io/hostname 값**과 Ready 상태를 확인 |
| `DATA_HOST_PATH` | 해당 Worker의 전용 데이터 경로. 신규 설치 기본값은 `/appdata/monitoring` |
| `DOCKER_REGISTRY`·`QUAY_REGISTRY`·`GHCR_REGISTRY`·`K8S_REGISTRY` | 사내 미러 경로. 저장소 기본값을 대조하고 [이미지 미러 설정](#이미지-미러-설정) 확인 |
| `IMAGE_PULL_SECRET` | 미러 인증이 필요할 때 사용할 기존 Kubernetes Secret 이름. 인증이 없으면 빈 값 |
| `INGRESS_ENABLED`·`INGRESS_HOST` | 기본값은 `true`, `etch.samsungds.net`. 이 도메인으로 웹 화면에 접속 |
| `NAMESPACE`·`GRAFANA_ADMIN_SECRET` | 기본값은 `monitoring`, `monitoring-grafana-admin`. [계정 준비](03-deploy.md#2-namespace와-관리자-secret-준비)에서 이 영역과 관리자 계정을 준비 |
| `INGRESS_TLS_SECRET` | 이전 설정 호환용. 기본값인 빈 값을 유지하고 인증서는 공용 Traefik에서 관리 |

이 문서의 명령은 기본 namespace와 Secret 이름을 사용합니다. 이름을 변경하면 명령에서도 함께 바꿉니다.
다른 env 파일을 쓰려면 `MONITORING_ENV`에 그 파일의 절대 경로를 export합니다.
다음 단계의 Make 명령과 Python 명령은 같은 파일을 사용합니다.

**폴더는 배포 시 자동 생성됩니다. 수동으로 만들 필요가 없습니다.**
다만 지정 Worker의 데이터 디스크가 의도한 위치에 마운트되어 있고 여유 공간이 있는지는 먼저 확인합니다.
폴더 생성은 디스크 마운트나 데이터 이전을 수행하지 않습니다. [저장소 상세](#저장소와-폴더-자동-생성)를 참고하세요.

## 저장소와 폴더 자동 생성

데이터는 `NODE_NAME` Worker의 `DATA_HOST_PATH` 아래에 저장합니다.
기본 경로는 `/appdata/monitoring`이며 **새로 생성하는 서비스 폴더**에는 아래 소유권과 권한 `0770`을 적용합니다.

| 서비스 폴더 | 소유 UID:GID | local PV 예약 용량 |
| --- | --- | ---: |
| `prometheus` | `1000:2000` | 20Gi |
| `alertmanager` | `1000:2000` | 2Gi |
| `grafana` | `472:472` | 5Gi |

local PV는 해당 노드의 폴더를 Kubernetes 데이터 볼륨으로 연결하는 방식이며 별도 StorageClass가 필요하지 않습니다.
예약 용량은 실제 디스크 할당이나 사용량 제한이 아닙니다. Prometheus 보존 기준은 7일 또는 16GB이고 WAL 등 추가 공간도 필요합니다.

기존 폴더·하위 데이터의 소유권과 권한은 보존합니다. 사용자 지정 UID/GID를 사용하면 폴더 권한도 직접 맞춥니다.
저장 경로가 일반 파일·심볼릭 링크이거나 기존 PV 폴더가 사라졌으면 중단합니다.
폴더 준비 실패 시 PV·Helm 배포로 넘어가지 않습니다.

PV의 reclaim policy는 `Retain`이며 정상 갱신 시 기존 PV·PVC·namespace를 삭제하지 않습니다.
Pod 재시작에도 데이터를 보존하지만 **지정 Worker 한 대에 저장하므로 고가용성 구성은 아닙니다.**
이전 경로 `/srv/monitoring`을 쓰던 서버는 데이터 이전이 끝나기 전까지 기존 env 경로를 유지합니다.
새 Kubernetes 설치는 기존 Compose의 지표 DB를 자동 복원하지 않습니다.

## 이미지 미러 설정

아래 네 종류의 미러를 사용합니다. 각 이미지가 실행될 노드에서 해당 미러에 접근할 수 있어야 합니다.
registry 값은 URL scheme 없이 `레지스트리/proxy경로`로 입력하며 끝에 `/`를 붙이지 않습니다.
실제 주소의 관리 원본은 [사내 저장소·미러](../../shared/docs/infrastructure/repositories.md)입니다.

| env 키 | 외부 원본 | 사용하는 이미지 |
| --- | --- | --- |
| `DOCKER_REGISTRY` | docker.io | Grafana, 폴더 준비용 `library/busybox:1.37.0` |
| `QUAY_REGISTRY` | quay.io | Prometheus·Operator·Alertmanager·node-exporter·Grafana sidecar·config reloader |
| `GHCR_REGISTRY` | ghcr.io | webhook 인증서 초기화 이미지 |
| `K8S_REGISTRY` | registry.k8s.io | kube-state-metrics |

Docker Hub 미러 하나만으로는 모든 이미지를 받을 수 없습니다.
[렌더 검사](03-deploy.md#1-원본실제-설정-검사)의 `images.txt` 전체를 확인하고, 미러에 없는 이미지·태그는 승인된 경로로 반입합니다.
`IMAGE_PULL_SECRET`에는 registry 인증 Secret의 **이름만** 입력합니다. Grafana 로그인용 Secret과는 별개입니다.

## 선택 설정

### port-forward로만 접속하기

공용 HTTPS 경로를 사용하지 않을 때는 env를 아래처럼 바꾼 뒤 [검사·배포](03-deploy.md#1-원본실제-설정-검사)를 진행합니다.
이 경우 배포 문서의 Traefik·인증서 준비는 생략하며, Grafana를 사용한다면 관리자 Secret은 여전히 필요합니다.

```dotenv
INGRESS_ENABLED=false
INGRESS_HOST=
INGRESS_TLS_SECRET=
```

설치 후 접속할 PC에서 kubeconfig를 준비하고, 같은 클러스터의 context를 지정해 실행합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-grafana 3000:80

# 다른 터미널에서 같은 context를 지정한 뒤 실행합니다.
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

주소는 `http://localhost:3000`, `http://localhost:9090/targets`입니다. 명령을 종료하면 연결도 종료됩니다.
기본 HTTPS 모드에서는 Grafana가 공개 도메인으로 리다이렉트하므로 공용 주소로 확인합니다.

### 일부 서비스를 끄거나 Helm 설정 추가하기

환경별 추가 설정은 비밀값 없는 values 파일로 작성합니다.
Make 기본 명령에는 추가 values 옵션이 없으므로, 필요한 경우 아래 명령으로 **검사·배포에 같은 파일**을 전달합니다.

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

비활성 Grafana·Prometheus·Alertmanager는 폴더 준비·신규 PV·준비 대기 대상에서 제외합니다.
기존 PV·PVC는 삭제하지 않고, Grafana가 꺼져 있으면 관리자 Secret도 조회하지 않습니다.
최종 values에서 모든 Ingress를 끄면 Traefik controller·TLS도 조회하지 않습니다.

**완료 기준:** 실제 env·데이터 위치·이미지 미러·접속 방식을 정했습니다. [검사·배포·검증](03-deploy.md)으로 이동합니다.
