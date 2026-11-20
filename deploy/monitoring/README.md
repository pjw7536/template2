# Monitoring 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

Prometheus·Grafana·Alertmanager(`kube-prometheus-stack`)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | Prometheus가 노드·Pod 지표를 수집하고 Grafana로 조회하는 클러스터 모니터링 |
| namespace | `monitoring` (Helm release `monitoring`, chart `kube-prometheus-stack` 91.4.0) |
| 실행 Worker | `khinfow01`, 데이터 `/appdata/monitoring`(없으면 `monitoring-up`이 생성). node-exporter는 모든 노드 |
| 공개 주소 | `https://grafana.etch.samsungds.net`, `https://prometheus.etch.samsungds.net`, `https://alert.etch.samsungds.net` |
| 배포 명령 | `make ops-deploy APP=monitoring` = `monitoring-check` → `monitoring-up` → `monitoring-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, Pod Ready, PVC Bound |
| 먼저 필요한 것 | chart 파일, 세 host의 공용 TLS, Helm 3.19 이상 |

## 구성

- 수집·조회: Operator·Prometheus·Alertmanager·Grafana·kube-state-metrics는 지정 Worker 한 대, node-exporter는 대상 노드마다 실행합니다. 새 Worker는 가입하면 자동으로 수집 대상에 포함됩니다.
- 기본 구성에 없는 것: etcd·scheduler·controller-manager·kube-proxy 수집과 Grafana SSO. Alertmanager 기본 수신자는 `null`이며 외부 통지를 보내지 않습니다.
- chart: [chart.lock.json](helm/chart.lock.json)에 버전과 SHA-256을 고정한 파일을 사용합니다. 검사·배포는 chart를 자동으로 내려받지 않습니다.
- 이미지: [env/k8s.env](env/k8s.env)의 docker.io·quay.io·ghcr.io·registry.k8s.io 사내 미러에서 받습니다.
- 접속: 공용 Traefik의 HTTPS entrypoint로 들어옵니다. Grafana는 `https://<GRAFANA_HOST>/`, Prometheus 수집 상태는 `https://<PROMETHEUS_HOST>/targets`, Alertmanager는 `https://<ALERTMANAGER_HOST>/`입니다. `monitoring-up`은 기존 VIP·다른 앱·Traefik 배치를 보존하면서 `monitoring` namespace의 라우팅 권한과 감시 범위만 추가합니다.
- 저장: 지정 Worker 한 대의 local PV(`Retain`)이며 고가용성 구성이 아닙니다. 서비스별 폴더와 용량은 [저장소와 폴더](docs/01-prepare.md#저장소와-폴더)에 있습니다.
- Kubernetes 1.25 이상이 필요하고, 폴더 준비 Job의 root·`hostPath`와 node-exporter의 `hostNetwork`·`hostPath`가 namespace 정책에서 허용되어야 합니다. Portal·Keycloak·Airflow 없이 설치할 수 있습니다.

배치 노드·서비스 주소는 [서비스·앱 배치](../shared/docs/infrastructure/services.md), 미러 주소는 [사내 저장소·미러](../shared/docs/infrastructure/repositories.md)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 사내 미러에서 chart를 받을 수 없을 때 chart 파일 반입([방법](docs/01-prepare.md#고정-chart-준비)) | `ls -l deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz` |
| 인증서 파일 배치(세 host가 SAN에 있어야 함) | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt deploy/shared/certs/etch.samsungds.net/private.key` |
| DNS 세 host → APP VIP 등록 | `getent hosts grafana.etch.samsungds.net prometheus.etch.samsungds.net alert.etch.samsungds.net` |
| 미러에 없는 이미지 반입([이미지 목록](docs/01-prepare.md#이미지-목록-확인)) | 배포 중 `ImagePullBackOff`가 나오면 요청 |
| 선택: Grafana 로그인(기본 홈 `/d/servers-overview`), Prometheus `/targets` 확인([기준](docs/02-operations.md#화면과-지표-확인)) | 사용자 보고 |

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

## A. 최초 설치

1. [검사] chart·인증서 파일 확인: 위 표의 `ls` 명령. chart가 없으면 [변경] `make monitoring-fetch-chart`를 실행하고, 받지 못하면 멈추고 반입을 요청합니다.
2. [변경] 공용 TLS 등록: `grafana.etch.samsungds.net`, `prometheus.etch.samsungds.net`, `alert.etch.samsungds.net`을 각각 사이트 폴더 `etch.samsungds.net`으로 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
3. [변경] 배포. namespace·Grafana 관리자 Secret·저장 폴더·local PV·Helm 설치(`--wait`)를 수행합니다.
   ```bash
   make ops-deploy APP=monitoring KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. `공용 TLS 마운트가 없습니다`로 실패하면 [공용 Traefik 갱신](../README.md#공용-traefik-검사갱신)의 `ingress-up` 뒤 다시 실행합니다.
4. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·values·대시보드 | [변경] `make ops-deploy APP=monitoring KUBE_CONTEXT="<context>"` |
| 대시보드 JSON | 먼저 `python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'` [검사]. [방법](docs/02-operations.md#대시보드-원본-갱신) |
| 인증서 | A-2 |
| chart 버전·`NODE_NAME`·`DATA_HOST_PATH` | 멈추고 사람에게 묻기(CRD 호환성·데이터 이전 필요). [기준](docs/02-operations.md#갱신운영) |
| Grafana 비밀번호 | [사람] Grafana UI에서 변경. Secret만 바꿔서는 반영되지 않음 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
helm --kube-context "<context>" -n monitoring list --all
kubectl --context "<context>" -n monitoring get pods,pvc,jobs
make monitoring-smoke KUBE_CONTEXT="<context>"
```

성공: release `deployed`, Pod Ready, PVC Bound, `smoke 통과: monitoring`.

## 문제 해결과 멈춤 조건

상태 조회 명령과 증상별 확인 내용은 [문제 해결](docs/02-operations.md#문제-해결), 모든 앱에 공통인 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

멈추고 사람에게 묻는 조건입니다.

- 기존 Prometheus Operator CRD가 있다는 오류, 기존 release의 chart 버전이 다르다는 오류
- 폴더 준비 Job 실패(root·hostPath·디스크), `ImagePullBackOff`
- node-exporter 9100 포트 충돌
- PVC·namespace·CRD 삭제가 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [준비와 설정](docs/01-prepare.md) | 준비 조건, 고정 chart 준비, 저장소와 폴더, 이미지 미러 설정과 이미지 목록 확인, Grafana 관리자 계정, 선택 설정(port-forward·추가 Helm values), 배포 도구의 처리 순서 |
| [운영 작업](docs/02-operations.md) | 변경 유형별 처리와 백업, 화면과 지표 확인, 알림 설정, 전체 서버 추세 대시보드와 원본 갱신, 문제 해결 |
