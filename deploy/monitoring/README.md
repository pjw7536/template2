# Monitoring 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Prometheus·Grafana·Alertmanager(`kube-prometheus-stack`)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | Prometheus가 노드·Pod 지표를 수집하고 Grafana로 조회하는 클러스터 모니터링 |
| namespace | `monitoring` (Helm release `monitoring`, chart `kube-prometheus-stack` 91.4.0) |
| 실행 Worker | `khinfow01`, 데이터 `/appdata/monitoring`(없으면 `monitoring-up`이 생성). node-exporter는 모든 노드 |
| 공개 주소 | `https://grafana.etch.samsungds.net`, `https://prometheus.etch.samsungds.net`, `https://alert.etch.samsungds.net` |
| 배포 명령 | `make ops-deploy APP=monitoring` = 준비 검사 → `monitoring-check` → `monitoring-up` → `monitoring-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, Pod Ready, PVC Bound, `smoke 통과: monitoring` |
| 먼저 필요한 것 | [공용 Traefik(ingress)](../shared/ingress/README.md) 배포, Helm 3.19 이상. chart 파일과 세 host의 공용 TLS는 준비 검사가 확인하고, 필요한 파일이 있으면 자동으로 준비 |

## 구성

- 수집·조회: Operator·Prometheus·Alertmanager·Grafana·kube-state-metrics는 지정 Worker 한 대, node-exporter는 대상 노드마다 실행합니다. 새 Worker는 가입하면 자동으로 수집 대상에 포함됩니다.
- 기본 구성에 없는 것: etcd·scheduler·controller-manager·kube-proxy 수집과 Grafana SSO. Alertmanager 기본 수신자는 `null`이며 외부 통지를 보내지 않습니다.
- chart: [chart.lock.json](helm/chart.lock.json)에 버전과 SHA-256을 고정한 파일을 사용합니다. 파일이 없으면 `ops-deploy`의 준비 검사가 사내 미러에서 받으며, `monitoring-check`·`monitoring-up`은 chart를 내려받지 않습니다.
- 이미지: [env/k8s.env](env/k8s.env)의 docker.io·quay.io·ghcr.io·registry.k8s.io 사내 미러에서 받습니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. Grafana는 `https://<GRAFANA_HOST>/`, Prometheus 수집 상태는 `https://<PROMETHEUS_HOST>/targets`, Alertmanager는 `https://<ALERTMANAGER_HOST>/`입니다. `monitoring-up`은 기존 VIP·다른 앱·Traefik 배치를 보존하면서 `monitoring` namespace의 라우팅 권한과 감시 범위만 추가합니다.
- 저장: 지정 Worker 한 대의 local PV(`Retain`)이며 고가용성 구성이 아닙니다. 서비스별 폴더와 용량은 [저장소와 폴더](docs/01-prepare.md#저장소와-폴더)에 있습니다.
- Kubernetes 1.25 이상이 필요하고, 폴더 준비 Job의 root·`hostPath`와 node-exporter의 `hostNetwork`·`hostPath`가 namespace 정책에서 허용되어야 합니다. Portal·Keycloak·Airflow 없이 설치할 수 있습니다.

배치 노드·서비스 주소는 [서비스·앱 배치](../shared/docs/infrastructure/services.md), 미러 주소는 [사내 저장소·미러](../shared/docs/infrastructure/repositories.md)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 같은 행의 준비 작업을 수행합니다. `자동`이라고 적은 준비는 `make ops-deploy`의 준비 검사가 실행하므로 따로 실행하지 않습니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 실행 Worker `khinfow01`이 `Ready`이고 cordon 상태가 아님. 차단 taint는 `monitoring-up`이 확인 | `kubectl --context "<context>" get node khinfow01` |
| 관리 호스트의 Helm이 3.19 이상 | `helm version --short` |
| chart 파일 `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz`. 자동: 없으면 사내 미러에서 받음. 미러에서 받지 못하면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입)으로 둠([방법](docs/01-prepare.md#고정-chart-준비)) | `make ops-preflight APP=monitoring KUBE_CONTEXT="<context>"`의 `chart` 줄이 `[통과]` 또는 `[자동 준비]` |
| 세 host를 SAN에 가진 `fullchain.crt`·`private.key`를 `deploy/shared/certs/etch.samsungds.net/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급)). 자동: 공용 TLS 등록 | `make ops-preflight APP=monitoring KUBE_CONTEXT="<context>"`의 `공용 TLS <host>` 세 줄이 `[통과]` 또는 `[자동 준비]` |
| DNS 세 host → APP VIP 등록. 없어도 배포는 진행하며 smoke가 `DNS 미등록`으로 표시 | `getent hosts grafana.etch.samsungds.net prometheus.etch.samsungds.net alert.etch.samsungds.net`. 빠진 host가 있으면 [DNS](../shared/docs/infrastructure/access.md#dns) |
| 실행 노드가 필요한 이미지를 사내 미러에서 받을 수 있음. 미러에 없는 이미지는 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입)([이미지 목록](docs/01-prepare.md#이미지-목록-확인)) | [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo -n crictl pull <images.txt의 이미지>'`를 실행 노드마다 실행 |
| `khinfow01`의 데이터 디스크가 마운트되어 있고 여유 공간이 있음 | [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py khinfow01 --context "<context>" --command 'df -h /appdata'`. 기준은 [디스크 확인](docs/01-prepare.md#저장소와-폴더) |
| 새 설치일 때 기존 Prometheus Operator가 없음 | `kubectl --context "<context>" get crd prometheuses.monitoring.coreos.com --ignore-not-found`의 출력이 없음 |
| 각 노드의 호스트 포트 9100을 다른 node-exporter가 쓰지 않음 | [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo -n ss -lntp "( sport = :9100 )"'`를 노드마다 실행한 출력에 LISTEN 줄이 없음 |

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `MONITORING_ENV` | Monitoring env 경로 | `deploy/monitoring/env/k8s.env`. 외부 경로면 모든 명령에 같은 값 |
| `MONITORING_GRAFANA_ENV` | Grafana 관리자 계정 파일. Secret `monitoring-grafana-admin`이 없을 때만 사용 | `deploy/monitoring/env/grafana-initial.env` |

env 파일의 키입니다.

| 키 | 의미 |
| --- | --- |
| `NAMESPACE` | 설치 namespace. 기본값 `monitoring` |
| `NODE_NAME` | 전체 스택을 실행할 Worker의 `kubernetes.io/hostname` 값 |
| `DATA_HOST_PATH` | 해당 Worker의 전용 데이터 경로. 신규 설치 기본값 `/appdata/monitoring` |
| `DOCKER_REGISTRY`·`QUAY_REGISTRY`·`GHCR_REGISTRY`·`K8S_REGISTRY` | 사내 미러 경로. scheme 없이 `레지스트리/proxy경로`로 입력하고 끝에 `/`를 붙이지 않음([이미지 미러 설정](docs/01-prepare.md#이미지-미러-설정)) |
| `IMAGE_PULL_SECRET` | 미러 인증이 필요할 때 사용할 기존 Kubernetes Secret 이름. 인증이 없으면 빈 값 |
| `GRAFANA_ADMIN_SECRET` | `admin-user`·`admin-password` 키를 가진 Grafana 관리자 Secret 이름. 기본값 `monitoring-grafana-admin`([Grafana 관리자 계정](docs/01-prepare.md#grafana-관리자-계정)) |
| `INGRESS_ENABLED` | `true`면 서비스별 도메인으로 HTTPS 접속, `false`면 port-forward 전용([선택 설정](docs/01-prepare.md#선택-설정)) |
| `GRAFANA_HOST`·`PROMETHEUS_HOST`·`ALERTMANAGER_HOST` | 서비스별 도메인. 서로 달라야 하며 port-forward 모드에서는 빈 값 |

이 문서의 명령은 기본 namespace와 Secret 이름을 사용합니다. 이름을 바꾸면 명령에서도 함께 바꿉니다.
저장소의 기본 env와 다른 값이 필요하면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일) 절의 방법으로 저장소 밖 env를 만들어 `MONITORING_ENV=<경로>`로 지정합니다.

## A. 최초 설치

1. [조회] 노드 확인
   ```bash
   kubectl --context "<context>" get node khinfow01
   ```
   성공: `Ready`.
2. [변경] 배포. 준비 검사(chart 받기·세 host의 공용 TLS 등록을 자동 실행) → 검사 → namespace·Grafana 관리자 Secret·저장 폴더·local PV·Helm 설치(`--wait`) → smoke → 대조 순서로 진행합니다.
   ```bash
   make ops-deploy APP=monitoring KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `Monitoring 배포 완료`가 있습니다.
   실패하면 JSON의 `failedStep`에 맞는 조치를 한 번 수행하고 같은 명령을 다시 실행합니다. 오류 문구별 조치는 [문제 해결과 멈춤 조건](#문제-해결과-멈춤-조건)에 있습니다.
   - `preflight`: `blocked`의 항목마다 `reference`가 가리키는 [접근 경로](../shared/docs/infrastructure/access.md) 절로 해결합니다. `chart`는 [chart 준비](docs/01-prepare.md#고정-chart-준비), `공용 TLS <host>`는 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급), `먼저 필요한 앱 ingress`는 [ingress 가이드](../shared/ingress/README.md)의 A를 따릅니다.
   - `monitoring-check`: 출력의 `오류:` 줄을 문제 해결 표에서 찾습니다.
   - `monitoring-up`: `공용 TLS 마운트가 없습니다`면 [공용 Traefik 검사·갱신](../README.md#공용-traefik-검사갱신)의 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`를 실행합니다. 기존 Operator CRD·chart 버전·PV 오류는 멈춤 조건입니다.
   - `monitoring-smoke`: `DNS 미등록`만 표시되고 `smoke 통과: monitoring`으로 끝나면 성공입니다. DNS 등록은 JSON의 `pending`에 남으며 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 수행합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·values·대시보드 | [변경] `make ops-deploy APP=monitoring KUBE_CONTEXT="<context>"`. 저장소 밖 env는 같은 명령에 `MONITORING_ENV=<경로>`를 붙임 |
| 대시보드 JSON | [검사] `python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'`가 통과하면 위 행의 [변경] 명령을 실행. [방법](docs/02-operations.md#대시보드-원본-갱신) |
| 인증서 | [변경] [공용 TLS 등록](../README.md#공용-tls-등록)의 명령으로 `grafana.etch.samsungds.net`, `prometheus.etch.samsungds.net`, `alert.etch.samsungds.net`을 각각 다시 등록 |
| chart 버전·`NODE_NAME`·`DATA_HOST_PATH` | [승인] [갱신 기준](docs/02-operations.md#갱신운영)으로 CRD 호환성·데이터 이전 필요 여부를 확인하고 적용 범위·영향을 보여 준 뒤 승인받아 실행 |
| Grafana 비밀번호 | [변경] [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 Grafana 화면에서 변경하고 새 비밀번호로 로그인을 확인. Secret만 바꾸면 Grafana DB의 기존 계정은 그대로 유지됨 |

`ops-deploy`를 실행한 행의 성공 확인은 A-2와 같습니다. JSON의 `failedStep`이 `null`, `driftResultCode`가 `0`이어야 합니다.

## C. 배포 후 확인

모두 [조회]입니다.

```bash
helm --kube-context "<context>" -n monitoring list --all
kubectl --context "<context>" -n monitoring get pods,pvc,jobs
make monitoring-smoke KUBE_CONTEXT="<context>"
```

성공: release `deployed`, Pod Ready, PVC Bound, `smoke 통과: monitoring`. host가 DNS에 없으면 `DNS 미등록. APP VIP 직접 접속: …` 줄과 `smoke 통과: monitoring (DNS 미등록 host <n>개)`로 끝나며 이것도 통과입니다. 남은 DNS 등록은 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 수행합니다.

[조회] Grafana 로그인과 기본 홈 `/d/servers-overview`, Prometheus `/targets`는 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 [화면과 지표 기준](docs/02-operations.md#화면과-지표-확인)을 확인합니다.

## 문제 해결과 멈춤 조건

상태 조회 명령과 그 밖의 증상은 [문제 해결](docs/02-operations.md#문제-해결), 모든 앱에 공통인 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `실제 값 필요: <키>` | env에 실제 값이 없습니다. [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일) 절로 그 키를 채운 env를 준비하고 `MONITORING_ENV=<경로>`로 지정 |
| `Helm chart 준비 필요`, `chart SHA-256 불일치` | [변경] `make monitoring-fetch-chart`. 다시 실패하면 [chart 준비](docs/01-prepare.md#고정-chart-준비). 다른 버전의 chart로 바꾸지 않음 |
| `Secret monitoring-grafana-admin이 없습니다` | `MONITORING_GRAFANA_ENV`가 가리키는 [계정 파일](docs/01-prepare.md#grafana-관리자-계정)이 없거나 형식이 다름. 파일을 준비해 같은 명령에 `MONITORING_GRAFANA_ENV=<경로>`를 붙임 |
| `공용 TLS 마운트가 없습니다` | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` 뒤 다시 실행 |
| `ImagePullBackOff`·`ErrImagePull` | 실패한 이미지를 [노드 명령 실행](../shared/docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo -n crictl pull <이미지>'`로 확인. 미러에 없으면 [파일 반입](../shared/docs/infrastructure/access.md#파일-반입) |
| `monitoring-storage-prepare-*` Job 실패 | [Job 로그](docs/02-operations.md#문제-해결)를 조회. root·hostPath 허용과 디스크 마운트를 확인 |
| smoke `DNS 조회 실패, APP VIP 직접 접속도 실패` | 서비스가 Ingress를 거쳐 응답하지 않음. Pod와 Ingress를 조회하고 [장애 조회](../README.md#장애-조회)의 404 / 503 행을 따름 |

다음이면 멈추고 보고합니다.

- `기존 Prometheus Operator CRD가 있습니다`: 다른 모니터링이 이미 있습니다. CRD를 삭제하거나 기존 Operator를 중지하지 않습니다.
- `기존 chart 버전이 다릅니다`: CRD upgrade 검토가 필요합니다. release를 지우거나 다른 chart 파일로 바꿔 통과시키지 않습니다.
- `기존 Monitoring PV의 경로·노드가 다릅니다` 또는 `기존 Monitoring PV가 다른 PVC에 예약되어 있습니다`: env의 `DATA_HOST_PATH`·`NODE_NAME`이 기존 저장소와 다릅니다. PV·PVC·데이터 폴더를 지우거나 옮기지 않습니다.
- 폴더 준비 Job이 `저장 경로가 디렉터리가 아니거나 심볼릭 링크입니다` 또는 `기존 PV의 저장 폴더가 없습니다`로 실패한 경우: 경로를 새로 만들거나 파일을 지우지 않습니다. 디스크 마운트와 데이터를 조회해 함께 보고합니다.
- node-exporter가 호스트 포트 9100 충돌로 기동하지 못하는 경우: 기존 node-exporter를 중지·삭제하지 않습니다.
- PVC·namespace·CRD 삭제나 `helm uninstall`이 필요해 보이는 경우: 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [준비와 설정](docs/01-prepare.md) | 준비 조건, 고정 chart 준비, 저장소와 폴더, 이미지 미러 설정과 이미지 목록 확인, Grafana 관리자 계정, 선택 설정(port-forward 전용 모드·추가 Helm values), 배포 도구의 처리 순서 |
| [운영 작업](docs/02-operations.md) | 변경 유형별 처리와 백업, 화면과 지표 확인, 알림 설정, 전체 서버 추세 대시보드와 원본 갱신, 문제 해결 |
