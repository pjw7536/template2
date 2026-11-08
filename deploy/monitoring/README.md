# Monitoring 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

클러스터의 노드·Pod 지표를 Prometheus로 수집하고 Grafana로 확인합니다.
Portal·Keycloak·Airflow가 없어도 설치할 수 있습니다. 기본 HTTPS 접속에는 공용 Traefik·DNS/VIP·도메인 인증서가 필요합니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업 | 완료 기준 |
| --- | --- | --- |
| 1 | [서버·chart 준비](docs/01-setup.md) | 도구·권한·Worker·고정 chart 준비 |
| 2 | [환경설정](docs/02-environment.md) | 실제 context·env·데이터 위치·미러·접속 방식 선택 |
| 3 | [검사·계정·HTTPS 준비와 배포](docs/03-deploy.md) | Pod Ready·PVC Bound·Grafana 로그인·실제 지표 확인 |

단계 번호는 각 문서 안에서 다시 시작합니다.
명령은 관리 서버의 저장소 루트에서 같은 Bash 터미널로 실행합니다.
새 터미널에서는 환경설정 문서의 `KUBE_CONTEXT`와 `MONITORING_ENV`를 다시 export합니다.
설치 명령은 관리 서버에서 한 번 수행하며 각 Worker에서 반복하지 않습니다.

## 운영·참고

| 하려는 일 | 문서 |
| --- | --- |
| 설정 갱신·백업·Worker 추가·장애 대응 | [운영 안내](docs/04-operations.md) |
| 저장 경로·이미지 미러·port-forward·추가 values | [환경설정과 선택 설정](docs/02-environment.md) |
| 전체 서버 추세 대시보드 | [대시보드 사용·설정](docs/03-deploy.md#전체-서버-추세-대시보드) |

## 무엇이 어디에 실행되나요?

| 구성 요소 | 하는 일 | 기본 실행 위치 |
| --- | --- | --- |
| Prometheus | 지표 수집·저장 | 지정한 Worker에 1개 |
| Grafana | 지표를 대시보드로 표시 | 같은 Worker에 1개 |
| Alertmanager | 알림 조건에 따른 통지 처리 | 같은 Worker에 1개 |
| Prometheus Operator | Prometheus·Alertmanager의 실행 상태 관리 | 같은 Worker |
| kube-state-metrics | Pod·Deployment 등 Kubernetes 리소스 상태 제공 | 같은 Worker |
| node-exporter | 노드의 CPU·메모리·디스크 지표 제공 | 배치 조건을 만족하는 노드마다 1개 |

**모든 Worker에 전체 스택을 설치할 필요는 없습니다.**
새 Worker가 클러스터에 가입하면 node-exporter가 DaemonSet으로 자동 배치되고 수집 대상에 포함됩니다.
새 Worker에서도 미러 이미지 pull과 지표 수집 통신이 가능해야 합니다.
데이터 저장 폴더는 Prometheus·Grafana·Alertmanager가 실행되는 지정 Worker에만 필요합니다.

기본 수집 범위는 노드·Pod·kubelet/cAdvisor·API server·CoreDNS입니다.
etcd·scheduler·controller-manager·kube-proxy는 endpoint·인증이 확정되지 않아 제외합니다.
애플리케이션 업무 지표, 로그, FTP 전송 성공 여부는 별도 수집 설정이 필요합니다.
Alertmanager의 기본 수신자는 `null`이므로 외부 메시지를 보내지 않으며, Grafana SSO도 기본 구성에 포함되지 않습니다.

## 파일과 참고 자료

| 파일 | 역할 |
| --- | --- |
| [env/k8s.env](env/k8s.env) | 배치 노드·데이터 경로·이미지 미러·Secret 이름·웹 주소 |
| [helm/chart.lock.json](helm/chart.lock.json) | 고정 chart 버전·다운로드 주소·SHA-256 |
| [helm/values.yaml](helm/values.yaml) | 기본 보존 기간·자원 요청량·수집 범위 등 Helm 설정 |
| [dashboards/servers-overview.json](dashboards/servers-overview.json) | 전체 서버 추세·상태 표·Grafana 기본 홈 |
| [scripts/manage.py](scripts/manage.py) | 다운로드·검사·렌더·폴더 준비·배포 실행 |

공식 참고: [kube-prometheus-stack 설치·CRD·업데이트](https://github.com/prometheus-community/helm-charts/tree/kube-prometheus-stack-91.4.0/charts/kube-prometheus-stack),
[Grafana 하위 경로 설정](https://grafana.com/tutorials/run-grafana-behind-a-proxy/),
[Prometheus external URL·route prefix](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/).
