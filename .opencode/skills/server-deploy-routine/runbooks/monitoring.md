# Monitoring 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/monitoring/README.md) · [설치](../../../../deploy/monitoring/docs/01-install.md) · [운영](../../../../deploy/monitoring/docs/02-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `monitoring` (Helm release `monitoring`, chart `kube-prometheus-stack` 91.4.0) |
| 실행 Worker | `khinfow01`, 데이터 `/appdata/monitoring`. node-exporter는 모든 노드 |
| 공개 주소 | `https://grafana.etch.samsungds.net`, `https://prometheus.etch.samsungds.net`, `https://alert.etch.samsungds.net` |
| 배포 명령 | `make monitoring-check` → `make monitoring-up` (성공 시 배포 기록 자동) |
| 완료 기준 | Pod Ready, PVC Bound, 사람이 Grafana 로그인·서버 그래프·Prometheus `/targets` UP 확인 |
| 먼저 필요한 것 | chart 파일, Grafana 관리자 Secret, 세 host의 공용 TLS, Helm 3.19 이상 |

## 사람이 해야 하는 일

- [사람] Grafana 관리자 계정 파일 작성(Git 밖, 키 `admin-user`, `admin-password`)
- [사람] DNS·인증서 파일, 미러에 없는 이미지 반입
- [사람] khinfow01 데이터 디스크 확인
- [사람] Grafana·Prometheus 화면 확인

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `MONITORING_ENV` | Monitoring env 경로 | `deploy/monitoring/env/k8s.env`. 외부 경로면 check·up·drift-check에 같은 값 |
| chart | `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz` | 없으면 A-2 |
| Grafana Secret | `monitoring/monitoring-grafana-admin` | 없으면 A-5 |

## A. 최초 설치

1. [사람] 계정 파일·DNS·인증서 준비를 사용자에게 확인합니다.
2. [변경] chart 준비(로컬 파일). 이미 있으면 생략합니다.
   ```bash
   ls -l deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz || python3 deploy/monitoring/scripts/manage.py fetch-chart
   ```
   성공: 파일이 있거나 `고정 chart 다운로드·SHA-256 검사 통과`. SHA-256 불일치면 멈춥니다.
3. [조회] 노드 확인
   ```bash
   kubectl --context kubernetes-admin@kubernetes get node khinfow01 -o wide
   ```
4. [검사] 원본·실제 설정 검사(클러스터 접속 없음)
   ```bash
   make server-check APP=monitoring PROFILE=prod
   make monitoring-check
   ```
   성공: `Monitoring Helm 원본 검사 통과`. `실제 값 필요: <키>`면 [사람]에게 env 입력을 요청하고 멈춥니다.
5. [변경] namespace와 Grafana 관리자 Secret(승인 필요). Secret이 이미 있으면 두 번째 명령은 생략합니다. 계정 파일 경로는 사용자에게 받습니다. 파일 내용은 읽지 않습니다.
   ```bash
   kubectl --context kubernetes-admin@kubernetes create namespace monitoring --dry-run=client -o yaml | kubectl --context kubernetes-admin@kubernetes apply -f -
   kubectl --context kubernetes-admin@kubernetes -n monitoring get secret monitoring-grafana-admin --ignore-not-found
   ```
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n monitoring create secret generic monitoring-grafana-admin --from-env-file=<Grafana 계정 파일 절대 경로>
   ```
6. [변경] 공용 TLS: `grafana.etch.samsungds.net`, `prometheus.etch.samsungds.net`, `alert.etch.samsungds.net`을 각각 [공통 TLS 등록](00-common.md#공용-tls-등록)으로 등록한 뒤 [공통 Traefik 갱신](00-common.md#공용-traefik-검사갱신)의 `ingress-up`을 합니다. 이미 등록돼 있으면 생략합니다.
7. [변경] 배포(승인 필요). 폴더 준비 Job, local PV, Helm 설치(`--wait`)를 수행합니다.
   ```bash
   make monitoring-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: 오류 없이 끝나고 `배포 기록 저장: monitoring/deploy-record-monitoring`.
8. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
9. [사람] Grafana 로그인(기본 홈 `/d/servers-overview`), Prometheus `/targets`, Alertmanager 화면 확인을 요청합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·values·대시보드 | A-4 → A-7 → C |
| 대시보드 JSON | 먼저 `python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'` [검사] |
| 인증서 | A-6 |
| chart 버전·`NODE_NAME`·`DATA_HOST_PATH` | 멈추고 사람에게 묻기(CRD 호환성·데이터 이전 필요) |
| Grafana 비밀번호 | 사람이 Grafana UI에서 변경. Secret만 바꿔서는 반영되지 않음 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
helm --kube-context kubernetes-admin@kubernetes -n monitoring list --all
kubectl --context kubernetes-admin@kubernetes -n monitoring get pods,pvc,jobs -o wide
kubectl --context kubernetes-admin@kubernetes -n monitoring get events --sort-by=.lastTimestamp
make drift-check APP=monitoring KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: release `deployed`, Pod Ready, PVC Bound, 폴더 준비 Job `Completed`(10분 뒤 자동 정리), drift-check 종료 코드 `0`.

## 멈추고 사람에게 묻는 조건

- 기존 Prometheus Operator CRD가 있다는 오류, 기존 release의 chart 버전이 다르다는 오류
- 폴더 준비 Job 실패(root·hostPath·디스크), `ImagePullBackOff`
- node-exporter 9100 포트 충돌
- PVC·namespace·CRD 삭제가 필요해 보이는 경우. 실행하지 않습니다.
