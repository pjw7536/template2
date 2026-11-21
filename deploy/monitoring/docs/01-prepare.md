# Monitoring 준비와 설정

[Monitoring 가이드](../README.md) · 다음: [운영 작업](02-operations.md)

설치·업데이트 절차는 [Monitoring 가이드](../README.md)에 있습니다. 이 문서는 입력 준비, 선택 설정과 배포 도구의 동작을 다룹니다.

- [준비 조건](#준비-조건)
- [고정 chart 준비](#고정-chart-준비)
- [저장소와 폴더](#저장소와-폴더)
- [이미지 미러 설정](#이미지-미러-설정)
- [이미지 목록 확인](#이미지-목록-확인)
- [Grafana 관리자 계정](#grafana-관리자-계정)
- [선택 설정](#선택-설정)
- [배포 도구의 처리 순서](#배포-도구의-처리-순서)

## 준비 조건

| 위치 | 준비할 것 |
| --- | --- |
| 관리 호스트 | 저장소, Python 3.10+, Helm 3.19+, kubectl, 클러스터 접속용 kubeconfig |
| Kubernetes | 버전 1.25+와 Operator CRD·ClusterRole·Job 등을 설치할 권한 |
| 지정 Worker | Ready 상태, 차단 taint 없음, 데이터 디스크·여유 공간, 사내 미러 접근 |
| 웹 접속 경로 | 기본 HTTPS 접속을 사용하면 공용 Traefik·도메인 인증서. DNS/VIP 등록은 없어도 배포되며 남은 일로 표시됨 |

- 폴더 준비 Job은 root 권한과 `hostPath`, node-exporter는 `hostNetwork`와 `hostPath`를 사용하므로 namespace 정책에서 허용되어야 합니다.
- 기존 Prometheus Operator가 있는 클러스터는 기존 모니터링을 사용할 수 있는지 먼저 확인합니다. 배포 도구는 새 설치에서 기존 Operator CRD를 발견하면 중단합니다.
- 현재 선언값은 [env/k8s.env](../env/k8s.env), 배치 대상 Worker의 확인 상태는 [서버 목록](../../shared/docs/infrastructure/servers.md#서버-목록)에서 확인합니다.

[조회] `NODE_NAME`에 넣을 hostname 값과 Ready 상태:

```bash
kubectl --context "<context>" get nodes -L kubernetes.io/hostname
kubectl --context "<context>" get node <NODE_NAME 값> -o wide
```

## 고정 chart 준비

`kube-prometheus-stack` **91.4.0** 패키지를 사용합니다. 버전과 SHA-256 `10d54f6984e5f97b2e96e64440c7c0c37af2ed1b17c1521fa6c0da3529bdeec1`은 [chart.lock.json](../helm/chart.lock.json)에 고정되어 있습니다.
chart 파일이 없으면 `make ops-deploy`의 준비 검사가 아래 명령을 자동으로 실행합니다.

[변경] chart만 따로 받을 때 관리 호스트에서 실행합니다. 이미 파일이 있으면 생략합니다.

```bash
make monitoring-fetch-chart
```

성공: `고정 chart 다운로드·SHA-256 검사 통과`. chart lock의 `proxy-raw-github.com` 미러에서 받아 SHA-256을 검증한 `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz`가 생깁니다. chart 파일은 Git에 커밋하지 않습니다.

실패: [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 같은 버전의 [공식 release 파일](https://github.com/prometheus-community/helm-charts/releases/download/kube-prometheus-stack-91.4.0/kube-prometheus-stack-91.4.0.tgz)을 관리 호스트의 같은 경로에 둡니다. 다른 위치에 두었다면 검사·배포·대조의 각 명령에 `MONITORING_CHART_FILE=/절대경로/kube-prometheus-stack-91.4.0.tgz`를 붙입니다.

[조회] 반입한 파일의 SHA-256이 lock의 값과 같은지 확인합니다.

```bash
sha256sum deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz
grep '"sha256"' deploy/monitoring/helm/chart.lock.json
```

성공: 두 줄의 해시가 같습니다.

`monitoring-check`·`monitoring-up`·렌더는 파일의 SHA-256을 확인하며 chart를 내려받지 않습니다. 의존 chart가 패키지에 포함되어 있으므로 `helm dependency update`를 실행하지 않습니다.

## 저장소와 폴더

데이터는 `NODE_NAME` Worker의 `DATA_HOST_PATH` 아래에 저장합니다. 폴더는 `monitoring-up`의 Job이 만들므로 수동으로 만들지 않습니다.
데이터 디스크가 의도한 위치에 마운트되어 있고 여유 공간이 있는지는 배포 전에 Worker에서 확인합니다.

[조회] 실행 위치는 `NODE_NAME` Worker(`khinfow01`)이며 관리 호스트에서 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--command`로 전달합니다. `/appdata`는 `DATA_HOST_PATH`(`/appdata/monitoring`)의 상위 폴더입니다.

```bash
df -h /appdata
```

성공: 의도한 데이터 디스크의 파일시스템이 표시되고 여유 공간이 아래 예약 용량의 합(27Gi)보다 큽니다.

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
- 기존 PV의 경로·노드가 env와 다르면 중단합니다. 기존 `DATA_HOST_PATH`·`NODE_NAME`을 유지하고, 옮길 때는 [변경 유형별 처리](02-operations.md#갱신운영)를 따릅니다.
- PV reclaim policy는 `Retain`이며 정상 갱신 시 PV·PVC·namespace를 삭제하지 않습니다. **지정 Worker 한 대에 저장하므로 고가용성 구성은 아닙니다.**

## 이미지 미러 설정

각 이미지가 실행될 노드에서 해당 미러에 접근할 수 있어야 합니다. registry 값은 URL scheme 없이 `레지스트리/proxy경로`로 입력하며 끝에 `/`를 붙이지 않습니다.
실제 주소의 관리 원본은 [사내 저장소·미러](../../shared/docs/infrastructure/repositories.md)입니다.

| env 키 | 외부 원본 | 사용하는 이미지 |
| --- | --- | --- |
| `DOCKER_REGISTRY` | docker.io | Grafana, 폴더 준비용 `library/busybox:1.37.0` |
| `QUAY_REGISTRY` | quay.io | Prometheus·Operator·Alertmanager·node-exporter·Grafana sidecar·config reloader |
| `GHCR_REGISTRY` | ghcr.io | webhook 인증서 초기화 이미지 |
| `K8S_REGISTRY` | registry.k8s.io | kube-state-metrics |

[이미지 목록 확인](#이미지-목록-확인)의 `images.txt` 전체를 확인하고, 미러에 없는 이미지·태그는 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 실행 노드에 반입합니다.
`IMAGE_PULL_SECRET`에는 registry 인증 Secret의 **이름만** 입력합니다. Grafana 로그인용 Secret과 별도로 `monitoring` namespace에 미리 등록합니다. 배포 도구는 이 Secret이 없으면 중단합니다.

## 이미지 목록 확인

[검사] 클러스터를 변경하지 않습니다. 외부 env를 쓰면 `make monitoring-check`와 `make monitoring-render`에 같은 `MONITORING_ENV=<경로>`를 붙입니다. 렌더 결과는 Git이 추적하지 않는 `.tools/render/monitoring` 아래에 씁니다.

```bash
make server-check APP=monitoring PROFILE=prod
make monitoring-check KUBE_CONTEXT="<context>"
make monitoring-render KUBE_CONTEXT="<context>"
cat .tools/render/monitoring/monitoring/images.txt
```

| 명령·파일 | 확인하는 내용 | 성공 문구 |
| --- | --- | --- |
| `server-check` | 저장소 기본 env와 chart의 정적 검사. 서버별 예제 값이 남아 있어도 통과할 수 있음 | `서버 원본 검사 통과: monitoring` |
| `monitoring-check` | 선택한 `MONITORING_ENV`의 필수 값·형식과 Helm 렌더 검사 | `Monitoring Helm 원본 검사 통과` |
| `monitoring-render` | 적용할 리소스를 파일로 생성. 설치는 하지 않음 | 만든 파일 경로(`monitoring.yaml`, `storage.json`) 출력 |
| `images.txt` | 실행에 필요한 전체 이미지. Operator가 만드는 이미지와 폴더 준비용 BusyBox도 포함 | 이미지 이름이 한 줄에 하나씩 출력 |

성공: 모든 명령이 통과하고 `images.txt`의 **모든 이미지·태그**를 각 실행 노드가 사내 미러에서 받을 수 있습니다. 렌더 성공만으로 실제 pull·디스크 권한·서버 보안 정책이 검증되지는 않습니다.
노드에서 이미지를 받을 수 있는지는 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo -n crictl pull <이미지>'`로 확인합니다.
렌더한 `monitoring.yaml`은 검토용이며 직접 `kubectl apply`하지 않습니다. CRD와 webhook 초기화 순서는 배포 도구가 관리합니다.
`deploy/monitoring` 아래에는 렌더 결과를 쓰지 않습니다. 추적되지 않는 파일이 생기면 배포 상태 대조가 `앱 경로의 미커밋 변경` 경고를 냅니다.

## Grafana 관리자 계정

`monitoring-up`이 Secret `monitoring-grafana-admin`이 없으면 계정 파일(`MONITORING_GRAFANA_ENV`, 기본 `deploy/monitoring/env/grafana-initial.env`)로 만듭니다. 기존 Secret은 바꾸지 않으며 `admin-user`·`admin-password` 키가 있는지만 확인합니다.

- 계정 파일에는 `admin-user`와 `admin-password`를 `키=값`으로 각각 한 번만 기록합니다. 값에 `export`나 감싸는 따옴표를 넣지 않습니다. 형식은 저장소의 [grafana-initial.env](../env/grafana-initial.env)와 같습니다.
- 별도 계정 파일을 쓰려면 Git 밖에 권한 600으로 두고 `make ops-deploy APP=monitoring KUBE_CONTEXT="<context>" MONITORING_GRAFANA_ENV=/절대경로/grafana.env`처럼 지정합니다.
- Helm은 Secret 이름을 참조합니다. Grafana DB가 만들어진 뒤에는 Secret만 바꿔도 비밀번호가 바뀌지 않으므로 [Grafana에서 갱신](02-operations.md#갱신운영)합니다.
- Grafana를 [선택 설정](#선택-설정)에서 비활성화했다면 관리자 Secret을 만들지 않습니다.

[조회] 현재 Secret 유무:

```bash
kubectl --context "<context>" -n monitoring get secret monitoring-grafana-admin --ignore-not-found
```

## 선택 설정

### port-forward로만 접속하기

공용 HTTPS 경로를 사용하지 않을 때는 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 env에서 아래 값을 지정합니다. Grafana는 로컬 관리자 로그인을 사용합니다.

```dotenv
INGRESS_ENABLED=false
GRAFANA_HOST=
GRAFANA_SSO_ENABLED=false
```

[조회] 이 모드에서는 공개 주소가 없으므로 API server가 Service로 전달하는 경로로 Grafana와 Prometheus의 상태를 조회합니다. 터미널을 점유하지 않고 바로 끝납니다.

```bash
kubectl --context "<context>" get --raw "/api/v1/namespaces/monitoring/services/monitoring-grafana:80/proxy/api/health"
kubectl --context "<context>" get --raw "/api/v1/namespaces/monitoring/services/monitoring-prometheus:9090/proxy/-/healthy"
```

성공: 첫 명령은 `database`가 `ok`인 JSON, 둘째 명령은 `Healthy`가 든 한 줄을 출력합니다.

아래는 PC 브라우저로 화면을 볼 때의 참고입니다. port-forward는 터미널을 점유하고 Ctrl+C로 종료해야 하므로 운영 agent의 절차에는 쓰지 않습니다. 두 명령은 서로 다른 터미널에서 같은 context로 실행합니다.

```text
kubectl --context "<context>" -n monitoring port-forward svc/monitoring-grafana 3000:80
kubectl --context "<context>" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

주소는 `http://localhost:3000`, `http://localhost:9090/targets`입니다. 기본 HTTPS 모드에서는 Grafana가 공개 도메인으로 리다이렉트하므로 공용 주소로 확인합니다.

### 일부 서비스를 끄거나 Helm 설정 추가하기

환경별 추가 설정은 비밀값 없는 values 파일로 작성합니다. Make 명령에는 추가 values 옵션이 없으므로 **검사·렌더·배포에 같은 파일**을 직접 전달합니다. values 파일은 저장소 밖에 두고, 렌더 결과도 Git이 추적하지 않는 `.tools/render/monitoring/monitoring`에 씁니다.

[검사]
```bash
python3 deploy/monitoring/scripts/manage.py check --env deploy/monitoring/env/k8s.env --values <추가 values 파일 절대 경로>
python3 deploy/monitoring/scripts/manage.py render --env deploy/monitoring/env/k8s.env \
  --values <추가 values 파일 절대 경로> --output .tools/render/monitoring/monitoring
```

성공: `Monitoring Helm 원본 검사 통과`와 `렌더 완료. images.txt의 모든 이미지를 사내 미러에서 확인하세요.`

[변경]
```bash
python3 deploy/monitoring/scripts/manage.py deploy --context "<context>" \
  --env deploy/monitoring/env/k8s.env --values <추가 values 파일 절대 경로>
```

성공: `Monitoring 배포 완료`.

추가 values가 env와 기본 설정을 덮어쓸 수 있으므로 최종 리소스·이미지 목록을 확인한 뒤 배포합니다.

[변경] `make monitoring-up`이 아닌 명령으로 배포했으므로 [배포 기록](../../shared/docs/operations/04-drift.md#배포-기록-남기기)을 남깁니다. 저장소 밖 env로 배포했으면 같은 `MONITORING_ENV=<경로>`를 붙입니다.

```bash
make deploy-record APP=monitoring KUBE_CONTEXT="<context>"
```

성공: `배포 기록 저장: monitoring/deploy-record-monitoring commit=<12자리>`.

Prometheus를 끄려면 고정 chart가 Prometheus 전용 token Secret을 참조하지 않도록 관련 감시도 함께 끕니다.

```yaml
prometheus:
  enabled: false
kubernetesServiceMonitors:
  enabled: false
```

비활성 서비스는 폴더 준비·신규 PV·준비 대기 대상에서 제외합니다. 기존 PV·PVC는 삭제하지 않고, Grafana가 꺼져 있으면 관리자 Secret을, 모든 Ingress가 꺼져 있으면 Traefik controller·TLS를 조회하지 않습니다.

## 배포 도구의 처리 순서

`monitoring-up`의 처리 순서는 다음과 같습니다.

1. 기존 Operator·chart 버전과 대상 노드를 확인하고, namespace와 Grafana 관리자 Secret이 없으면 만든 뒤 HTTPS 설정을 확인합니다.
2. 지정 Worker에서 없는 저장 폴더를 생성하는 Job을 실행하고 완료를 기다립니다.
3. 데이터 볼륨을 연결하고 Helm으로 모니터링을 설치하거나 갱신합니다.
4. Helm `--wait`와 Operator가 만드는 Prometheus·Alertmanager StatefulSet의 준비를 기다리고 공용 웹 경로를 연결합니다.

준비 Job은 `Completed`가 정상이며 완료·실패 후 10분 뒤 자동 정리됩니다. 실패하면 [문제 해결](02-operations.md#문제-해결)을 따릅니다.
설치 실패 시 도구는 DB·namespace를 자동 삭제하지 않습니다.
