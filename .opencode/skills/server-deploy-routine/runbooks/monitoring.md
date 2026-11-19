# Monitoring 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.

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

- [사람] 기존 Grafana 계정 사용 여부 확인. 신규 계정 파일은 `deploy/monitoring/env/grafana-initial.env`에 준비되어 있음
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
2. [검사] 공통 사전 검사에서 선택한 chart가 통과했는지 확인합니다. 차단 상태면 관리 호스트 준비 (사람용 `deploy/shared/docs/operations/04-drift.md#관리-호스트-준비`)에 따라 담당자가 chart를 준비한 뒤 같은 입력으로 재검사합니다.
3. [조회] 노드 확인
   ```bash
   kubectl --context "<context>" get node khinfow01 -o wide
   ```
4. [검사] 공통 사전 검사의 실제 env·원본 결과를 확인합니다. 준비 중 파일이 바뀌었으면 같은 입력으로 재검사합니다.
5. [변경] namespace와 Grafana 관리자 Secret(승인 필요). [사람]에게 monitoring-grafana-admin 등록 여부를 확인하고 이미 있으면 Secret 생성은 생략합니다. 별도 입력을 지정한 경우에만 아래 기본 파일 경로를 바꿉니다. 파일 내용은 읽지 않습니다.
   ```bash
   kubectl --context "<context>" create namespace monitoring --dry-run=client -o yaml | kubectl --context "<context>" apply -f -
   ```
   ```bash
   kubectl --context "<context>" -n monitoring create secret generic monitoring-grafana-admin --from-env-file=deploy/monitoring/env/grafana-initial.env
   ```
6. [변경] 공용 TLS: `grafana.etch.samsungds.net`, `prometheus.etch.samsungds.net`, `alert.etch.samsungds.net`을 각각 [공통 TLS 등록](00-common.md#공용-tls-등록)으로 등록한 뒤 [공통 Traefik 갱신](00-common.md#공용-traefik-검사갱신)의 `ingress-up`을 합니다. 이미 등록돼 있으면 생략합니다.
7. [변경] 배포(승인 필요). 폴더 준비 Job, local PV, Helm 설치(`--wait`)를 수행합니다.
   ```bash
   make monitoring-up KUBE_CONTEXT="<context>"
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
helm --kube-context "<context>" -n monitoring list --all
kubectl --context "<context>" -n monitoring get pods,pvc,jobs -o wide
kubectl --context "<context>" -n monitoring get events --sort-by=.lastTimestamp
```

성공: release `deployed`, Pod Ready, PVC Bound, 폴더 준비 Job `Completed`(10분 뒤 자동 정리), 공통 마무리의 JSON 판정 `0`.

## 멈추고 사람에게 묻는 조건

- 기존 Prometheus Operator CRD가 있다는 오류, 기존 release의 chart 버전이 다르다는 오류
- 폴더 준비 Job 실패(root·hostPath·디스크), `ImagePullBackOff`
- node-exporter 9100 포트 충돌
- PVC·namespace·CRD 삭제가 필요해 보이는 경우. 실행하지 않습니다.
