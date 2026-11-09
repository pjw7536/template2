# Monitoring 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

Prometheus로 노드·Pod 지표를 수집하고 Grafana로 조회합니다. 전체 스택은 지정 Worker 한 대, node-exporter는 대상 노드마다 실행합니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [chart·미러·저장소·Grafana 계정·HTTPS·배포·검증](docs/01-install.md) |
| 2 | [갱신·백업·새 Worker·장애 대응](docs/02-operations.md) |

etcd·scheduler·controller-manager·kube-proxy 수집과 Grafana SSO는 기본 구성에 없습니다. Alertmanager 기본 수신자는 `null`이며 외부 통지를 보내지 않습니다.
