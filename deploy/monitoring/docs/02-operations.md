# Monitoring 운영 작업

[Monitoring 가이드](../README.md) · [준비와 설정](01-prepare.md)

설치·업데이트 절차는 [Monitoring 가이드](../README.md)에 있습니다. 이 문서는 변경 유형별 처리 기준, 화면 확인, 대시보드 관리, 문제 해결입니다.

- [갱신·운영](#갱신운영)
- [화면과 지표 확인](#화면과-지표-확인)
- [알림 설정](#알림-설정)
- [전체 서버 추세 대시보드](#전체-서버-추세-대시보드)
- [문제 해결](#문제-해결)

## 갱신·운영

설정을 바꾼 뒤의 검사·재적용은 [가이드 B](../README.md#b-업데이트)의 명령으로 합니다. 외부 env·chart 경로를 쓰면 처음 설치할 때와 같은 값을 각 명령에 붙입니다.
새 Worker는 정상 가입 후 자동으로 수집 대상에 포함되므로 Worker 추가만으로 재배포할 필요는 없습니다.
기존 node-exporter가 호스트 포트 `9100`을 사용한다면 새 DaemonSet과 충돌합니다. 이 경우는 [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)이며 기존 node-exporter를 중지하지 않습니다.

| 변경할 내용 | 처리 방법 |
| --- | --- |
| 같은 chart 버전의 설정 | [변경] 가이드 B의 명령으로 검사 후 재적용 |
| chart 버전 | [승인] 도구가 다른 버전의 기존 release를 발견하면 중단. CRD 호환성과 공식 upgrade 절차를 먼저 검토 |
| Worker·데이터 경로 | [승인] 기존 local PV는 일반 재배포로 위치를 변경할 수 없음. [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전) 수행. `/srv/monitoring`을 쓰는 서버는 이전이 끝날 때까지 env의 `DATA_HOST_PATH`를 기존 경로로 유지 |
| Grafana 관리자 비밀번호 | [변경] Grafana DB 생성 후에는 Secret만 바꿔도 기존 비밀번호가 변경되지 않음. [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 Grafana 화면에서 갱신하고 새 비밀번호로 로그인을 확인 |
| 백업 | Grafana DB·대시보드·지표를 별도 디스크에 보관. 같은 노드의 데이터만으로 노드 장애를 복구할 수 없음. Compose 시절 지표 DB는 자동 복원되지 않음 |

설치 실패 시 도구는 DB·namespace를 자동 삭제하지 않습니다. 일부만 설치됐다면 Helm release 상태와 CRD·Job·Pod를 확인하고 원인을 해결한 뒤 같은 설정으로 재실행합니다.
기존 데이터를 지키기 위해 PVC·namespace·CRD를 임의 삭제하지 않습니다.

## 화면과 지표 확인

[가이드 C](../README.md#c-배포-후-확인)가 통과한 뒤 화면과 실제 지표를 확인합니다. 주소는 [서비스 접속 주소](../../shared/docs/infrastructure/services.md#서비스-접속-주소)에 있습니다.
세 주소의 HTTPS 응답은 `make monitoring-smoke KUBE_CONTEXT="<context>"`가 확인합니다. 로그인과 화면 내용은 [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다.

| 확인할 곳 | 정상 기준 |
| --- | --- |
| Grafana | 관리자 계정으로 로그인. 기본 홈 [전체 서버 · 리소스 추세](#전체-서버-추세-대시보드)에 서버별 그래프와 상태 표가 표시됨 |
| Prometheus `/targets` | 수집 대상이 `UP`. `DOWN`인 대상은 endpoint·권한·통신 확인 |
| Alertmanager | 웹 화면과 현재 알림 설정 확인. 기본값은 외부 통지 없음 |

확인한 실제 배치·접속 결과는 [서비스·앱 배치](../../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에 기록합니다.

## 알림 설정

Alertmanager의 기본 수신자는 `null`이며 외부 통지를 보내지 않습니다. 알림은 namespace·alertname으로 묶이고 Alertmanager 웹 화면에서 확인합니다.
외부 전송은 운영 수신자·채널을 정한 뒤 [values.yaml](../helm/values.yaml)의 `alertmanager.config`에 구성하고 [가이드 B](../README.md#b-업데이트)로 재적용합니다.

## 전체 서버 추세 대시보드

Grafana 기본 홈은 **전체 서버 · 리소스 추세**입니다. `/d/servers-overview`로 직접 열거나 Dashboards에서 제목으로 찾습니다. 개인·조직에서 별도 홈 대시보드를 지정했다면 그 설정이 우선합니다.

- 상단 요약: 등록 서버 수, 수집 정상·중단 수, CPU·메모리·디스크 최고 사용률.
- 비교 추세: 선택 서버의 CPU·메모리·디스크 사용률과 네트워크 처리량을 같은 시간축에서 비교. 범례에서 서버별 현재값·최댓값 확인.
- 현재 상태 표: 서버별 수집 상태, Kubernetes Ready, CPU·메모리·디스크·네트워크 수치.
- 상세 추세: 서버별 디스크 읽기·쓰기와 네트워크 수신·송신량.

기본 조회 기간은 최근 6시간, 갱신은 30초입니다. `서버`에서 전체 또는 여러 서버를, `네트워크 인터페이스`에서 장치를 고릅니다. bond와 하위 인터페이스를 함께 선택하면 네트워크가 중복 합산될 수 있습니다.

서버 목록은 kube-state-metrics의 등록 노드이며 node-exporter 지표를 Pod의 실제 노드명에 연결합니다. 수집 중단·exporter 미설치 서버도 상태 표에 남으며 사용량은 `미수집`으로 표시합니다.
CPU는 idle을 제외한 사용률, 메모리는 MemAvailable 기준, 디스크는 쓰기 가능한 실제 파일시스템 중 가장 높은 사용률입니다. 가상 파일시스템·Pod 마운트와 가상 네트워크 인터페이스를 제외하며, 디스크 I/O는 파티션·논리 장치를 제외한 물리 장치 합계입니다.

### 대시보드 원본 갱신

1. 공급 대시보드의 원본은 저장소의 [servers-overview.json](../dashboards/servers-overview.json)이며 변경은 저장소 갱신(`git pull --ff-only`)으로 받습니다. 운영 화면에서 개인용 변경이 필요할 때는 Grafana에서 복사본을 만들어 편집합니다.
2. [검사] 회귀 검사를 실행합니다. `promtool`이 PATH에 있거나 `PROMTOOL_COMMAND`(셸 실행 없는 명령 인자 문자열)로 지정되면 실제 PromQL fixture로 사용률·중복 수집·장치 필터·수집 중단 계산까지 확인합니다.

   ```bash
   python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'
   ```

3. [변경] 같은 env·context로 재적용합니다. Helm의 ConfigMap과 Grafana provisioning에 반영되며 별도 이미지 빌드·인터넷 템플릿 다운로드는 필요하지 않습니다.

   ```bash
   make ops-deploy APP=monitoring KUBE_CONTEXT="<context>"
   ```

성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. Grafana Pod가 재시작되고 기본 홈에 변경 내용이 표시됩니다([화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인)). 기본 Kubernetes 대시보드도 계속 사용할 수 있습니다.

## 문제 해결

[조회] 먼저 상태와 최근 이벤트를 확인합니다.

```bash
helm --kube-context "<context>" -n monitoring list --all
kubectl --context "<context>" -n monitoring get pods,pvc,jobs -o wide
kubectl --context "<context>" -n monitoring get events --sort-by=.lastTimestamp
```

| 증상·메시지 | 확인할 내용 |
| --- | --- |
| `실제 값 필요: <키>` | env에 `replace-me`·`example.invalid` 예시 값이 남았는지 확인하고 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 env에 실제 값을 넣어 `MONITORING_ENV=<경로>`로 지정 |
| `Helm chart 준비 필요` | [chart 준비](01-prepare.md#고정-chart-준비)의 파일 위치와 `MONITORING_CHART_FILE` 확인 |
| `chart SHA-256 불일치` | 고정 버전 패키지를 다시 준비. 임의 chart로 대체하지 않음 |
| `Secret monitoring-grafana-admin이 없습니다` | `MONITORING_GRAFANA_ENV`가 가리키는 [계정 파일](01-prepare.md#grafana-관리자-계정) 확인 |
| 기존 Operator CRD·다른 chart 버전 | 기존 모니터링·release 확인. CRD를 삭제해 우회하지 않음 |
| `ImagePullBackOff`·`ErrImagePull` | 실패한 이미지의 미러 경로·태그·노드 CA·접근 권한·pull Secret 확인. BusyBox도 포함. [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)로 그 노드에서 `sudo -n crictl pull <이미지>`로 재현. 미러에 없으면 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) |
| `monitoring-storage-prepare-*` 실패 | 아래 Job 로그와 Pod Events 확인. root·hostPath 허용, 디스크 마운트, 파일·심볼릭 링크 점유 확인 |
| 기존 PV 경로·노드·PVC 오류 | env를 기존 저장소 설정과 대조. 기존 PV 폴더가 사라졌으면 [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)로 마운트·데이터를 조회해 보고. PV·PVC·폴더를 새로 만들지 않음 |
| `Pending`·PVC 미결합 | 지정 Worker Ready·taint·자원 여유, PV/PVC 연결 상태 확인 |
| Grafana 데이터 폴더 권한 오류 | [노드 SSH](../../shared/docs/infrastructure/access.md#노드-ssh)로 기존 폴더의 UID/GID 확인([기준](01-prepare.md#저장소와-폴더)). 자동 생성은 기존 파일 권한을 변경하지 않음 |
| 화면 접속 실패 | `make monitoring-smoke KUBE_CONTEXT="<context>"`로 구간 확인. `DNS 미등록`이면 [DNS](../../shared/docs/infrastructure/access.md#dns), 그 밖에는 443 경로([방화벽](../../shared/docs/infrastructure/access.md#방화벽)), 공용 Traefik·인증서·서비스별 HOST 입력 확인 |
| 새 Worker 지표 없음 | 해당 노드의 node-exporter Pod, 미러 pull, `9100` 통신([방화벽](../../shared/docs/infrastructure/access.md#방화벽))과 Prometheus target 확인 |

[조회] 폴더 준비 Job이 실패했다면 **출력된 실제 Job 이름**으로 확인합니다.

```bash
kubectl --context "<context>" -n monitoring describe job <실패한 준비 Job 이름>
kubectl --context "<context>" -n monitoring get pods -l "job-name=<실패한 준비 Job 이름>"
kubectl --context "<context>" -n monitoring logs "job/<실패한 준비 Job 이름>"
```
