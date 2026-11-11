# Monitoring 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

고정 `kube-prometheus-stack` chart로 Prometheus가 노드·Pod 지표를 수집하고 Grafana로 조회합니다.
Operator·Prometheus·Alertmanager·Grafana·kube-state-metrics는 지정 Worker 한 대, node-exporter는 대상 노드마다 실행합니다.
etcd·scheduler·controller-manager·kube-proxy 수집과 Grafana SSO는 기본 구성에 없습니다. Alertmanager 기본 수신자는 `null`이며 외부 통지를 보내지 않습니다.

## 의존 서비스

| 대상 | 필요한 것 |
| --- | --- |
| chart | [chart.lock.json](helm/chart.lock.json)에 고정한 chart 파일 |
| 이미지 | [env/k8s.env](env/k8s.env)의 docker.io·quay.io·ghcr.io·registry.k8s.io 사내 미러 |
| Kubernetes | 1.25+, 지정 Worker의 데이터 디스크, root·`hostPath`·`hostNetwork` 허용 |
| 공용 Traefik | 기본 HTTPS 모드에서 서비스별 host의 TLS 등록. port-forward 모드는 불필요 |

Portal·Keycloak·Airflow 없이 설치할 수 있습니다.

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [chart·env·Grafana 계정·HTTPS·배포·검증](docs/01-install.md) |
| 2 | [갱신·대시보드·백업·장애 대응](docs/02-operations.md) |

## 완료 기준

Pod가 Ready이고 데이터 PVC가 Bound이며, Grafana 로그인 후 기본 홈 대시보드에 서버별 지표가 표시되고 Prometheus `/targets`의 수집 대상이 `UP`입니다.

## 운영 정보

배치 노드·서비스 주소는 [서비스·앱 배치](../shared/docs/infrastructure/services.md), 미러 주소는 [사내 저장소·미러](../shared/docs/infrastructure/repositories.md)에서 관리합니다.
