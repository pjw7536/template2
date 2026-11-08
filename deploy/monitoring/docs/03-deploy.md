# Monitoring 검사·배포·검증

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

[환경설정](02-environment.md)에서 `KUBE_CONTEXT`와 `MONITORING_ENV`를 export한 같은 Bash 터미널을 사용합니다. 다른 chart 경로를 선택했다면 `MONITORING_CHART_FILE`도 유지합니다. 검사 → 계정·HTTPS 준비 → 배포 순서로 진행합니다.

## 1. 원본·실제 설정 검사

관리 서버에서 다음 명령을 실행합니다. **이 단계는 클러스터를 변경하지 않습니다.**

```bash
make server-check APP=monitoring PROFILE=prod
make monitoring-check
python3 deploy/monitoring/scripts/manage.py render \
  --env "$MONITORING_ENV" --output deploy/monitoring/rendered
cat deploy/monitoring/rendered/images.txt
```

| 명령·파일 | 확인하는 내용 |
| --- | --- |
| `server-check` | 저장소 기본 env와 chart의 정적 검사. 서버별 예제 값이 남아 있어도 통과할 수 있음 |
| `monitoring-check` | 선택한 실제 env의 필수 값·형식과 Helm 렌더 검사 |
| `render` | 적용할 리소스를 파일로 생성. 설치는 하지 않음 |
| `images.txt` | 실행에 필요한 전체 이미지. Operator가 만드는 이미지와 폴더 준비용 BusyBox도 포함 |

`images.txt`의 **모든 이미지·태그**를 각 실행 노드가 사내 미러에서 받을 수 있어야 합니다.
렌더 성공만으로 실제 pull·디스크 권한·서버 보안 정책이 검증되지는 않습니다.

`rendered/monitoring.yaml`은 검토용입니다. 이 파일을 직접 `kubectl apply`하지 않습니다.
실제 설치는 [배포와 확인](#3-배포와-확인)의 Helm 명령이 CRD와 webhook 초기화 순서를 관리합니다.

## 2. Namespace와 관리자 Secret 준비

### Grafana 로그인 계정 등록

Namespace는 모니터링 리소스를 모아두는 설치 영역이고, Secret은 계정 정보를 전달하는 Kubernetes 리소스입니다.
먼저 관리 서버에서 설치 영역을 준비합니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace monitoring --dry-run=client -o yaml \
  | kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n monitoring get secret monitoring-grafana-admin --ignore-not-found
```

`monitoring-grafana-admin`이 이미 있으면 기존 계정을 사용하고 **아래 생성 단계는 생략**합니다.
처음 설치한다면 [관리자 env 샘플](../env/grafana-admin.env.example)을 Git 저장소 밖으로 복사하고 실제 계정으로 편집합니다.

```bash
read -r -p 'Grafana 관리자 env 파일 절대 경로: ' GRAFANA_CREDENTIAL_FILE
(
  set -e
  umask 077
  if [ ! -e "$GRAFANA_CREDENTIAL_FILE" ]; then
    cp deploy/monitoring/env/grafana-admin.env.example "$GRAFANA_CREDENTIAL_FILE"
  fi
  vi "$GRAFANA_CREDENTIAL_FILE"
)
chmod 600 "$GRAFANA_CREDENTIAL_FILE"
```

샘플의 아래 두 키를 실제 로그인 계정으로 채우고 예시 비밀번호를 교체합니다. `export`나 값을 감싸는 따옴표는 넣지 않습니다.

```dotenv
admin-user=
admin-password=
```

저장한 파일로 Secret을 만듭니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n monitoring create secret generic monitoring-grafana-admin \
  --from-env-file="$GRAFANA_CREDENTIAL_FILE"
```

관리자 비밀번호는 Helm values나 Git에 넣지 않습니다.
Grafana를 [선택 설정](02-environment.md#선택-설정)에서 비활성화했다면 namespace만 준비하고 관리자 Secret 등록은 생략합니다.
`IMAGE_PULL_SECRET`을 지정했다면 registry 인증용 Secret도 이 namespace에 미리 등록되어 있어야 합니다.

### HTTPS 웹 접속 준비

기본 설정은 공용 Traefik을 통해 아래 주소로 접속합니다.

| 화면 | 기본 주소 |
| --- | --- |
| Grafana | `https://etch.samsungds.net/grafana/` |
| Prometheus 수집 상태 | `https://etch.samsungds.net/prometheus/targets` |
| Alertmanager | `https://etch.samsungds.net/alertmanager/` |

접속 PC에서 이 도메인이 공용 진입점으로 연결되어야 하며, 인증서에도 도메인이 포함되어야 합니다.
`INGRESS_HOST`를 바꿨다면 주소와 아래 `TLS_HOST`도 같은 도메인으로 바꿉니다.

**공용 Traefik과 도메인 인증서가 이미 준비되어 있으면 다음 등록 명령은 생략합니다.**
처음 준비한다면 [공용 진입점 준비](../../shared/docs/ingress/README.md)에 따라 설정한 뒤 실행합니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MONITORING_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MONITORING_TLS_KEY
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$MONITORING_TLS_CERT" TLS_KEY_FILE="$MONITORING_TLS_KEY"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

배포 도구는 인증서와 controller 변경 권한을 확인합니다.
설치 후 기존 VIP·다른 앱·Traefik 배치를 보존하면서 Monitoring namespace의 라우팅 권한과 감시 범위를 추가합니다.
공용 HTTPS 접속을 사용하지 않으려면 [port-forward로만 접속하기](02-environment.md#port-forward로만-접속하기)를 먼저 적용합니다.

## 3. 배포와 확인

관리 서버에서 한 번 실행합니다. 각 Worker에서 반복 실행하지 않습니다.

```bash
make monitoring-up
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods,pvc -o wide
```

배포 도구가 진행하는 순서는 다음과 같습니다.

1. 기존 Operator·chart 버전, 대상 노드, 관리자 Secret, HTTPS 설정을 확인합니다.
2. 지정 Worker에서 없는 저장 폴더를 생성하는 Job을 실행하고 완료를 기다립니다.
3. 데이터 볼륨을 연결하고 Helm으로 모니터링을 설치하거나 갱신합니다.
4. 활성 서비스의 준비 상태를 기다리고 공용 웹 경로를 연결합니다.

일반 리소스는 Helm의 `--wait`로 확인하고, Operator가 나중에 만드는 Prometheus·Alertmanager의 StatefulSet도 생성·준비를 기다립니다.
준비 Job은 `Completed`가 정상이며 완료·실패 후 10분 뒤 자동 정리됩니다.

**설치 완료는 화면과 실제 지표까지 확인한 상태입니다.**

| 확인할 곳 | 정상 기준 |
| --- | --- |
| `get pods,pvc` | 실행할 Pod가 Ready이고 데이터 PVC가 Bound |
| Grafana | [앞에서 등록한 관리자 계정](#grafana-로그인-계정-등록)으로 로그인. 기본 홈인 `전체 서버 · 리소스 추세`에서 서버별 그래프와 상태 표에 지표가 표시됨 |
| Prometheus `/prometheus/targets` | 수집 대상이 `UP`. `DOWN`인 대상은 endpoint·권한·통신 확인 |
| Alertmanager | 웹 화면과 현재 알림 설정 확인. 기본값은 외부 통지 없음 |

### 전체 서버 추세 대시보드

기본 홈은 **전체 서버 · 리소스 추세**입니다. `/grafana/d/servers-overview`로 직접 열거나 Dashboards에서 제목으로 찾을 수 있습니다.
개인·조직에서 별도 홈 대시보드를 지정했다면 그 설정이 우선합니다.

- 상단 요약: 등록 서버 수, 수집 정상·중단 수, CPU·메모리·디스크 최고 사용률.
- 비교 추세: 모든 선택 서버의 CPU·메모리·디스크 사용률과 네트워크 처리량을 같은 시간축에서 비교. 범례에서 서버별 현재값·최댓값 확인.
- 현재 상태 표: 서버별 수집 상태, Kubernetes Ready, CPU·메모리·디스크·네트워크 수치.
- 상세 추세: 서버별 디스크 읽기·쓰기와 네트워크 수신·송신량.

기본 조회 기간은 최근 6시간, 갱신은 30초입니다. `서버`에서 전체 또는 여러 서버를 선택할 수 있고,
`네트워크 인터페이스`에서 필요한 장치를 고를 수 있습니다. bond와 하위 인터페이스를 함께 선택하면 네트워크가 중복 합산될 수 있습니다.

서버 목록은 kube-state-metrics의 등록 노드이며, node-exporter 지표를 Pod의 실제 노드명에 연결합니다.
수집 중단·exporter 미설치 서버도 상태 표에 남으며 사용량은 `미수집`으로 표시합니다.
CPU는 idle을 제외한 사용률, 메모리는 MemAvailable 기준, 디스크는 쓰기 가능한 실제 파일시스템 중 가장 높은 사용률입니다.
가상 파일시스템·Pod 마운트와 가상 네트워크 인터페이스를 제외하며, 디스크 I/O는 파티션·논리 장치를 제외한 물리 장치 합계입니다.

대시보드 원본은 [servers-overview.json](../dashboards/servers-overview.json)입니다.
Git의 JSON을 변경하고 같은 env·context로 `make monitoring-check` → `make monitoring-up`을 실행하면
Helm의 ConfigMap과 Grafana provisioning에 반영됩니다. 별도 이미지 빌드·인터넷 템플릿 다운로드가 필요하지 않습니다.
기본 Kubernetes 대시보드도 계속 사용할 수 있습니다. 공급된 대시보드는 JSON 원본에서 관리하고,
개인 화면은 Grafana에서 복사해 편집합니다.

대시보드 공급 검증은 기존 Monitoring 회귀 검사에 포함됩니다. `promtool`이 PATH에 있으면
`python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'`에서
실제 PromQL fixture로 사용률·중복 수집·장치 필터·수집 중단 계산까지 확인합니다.
별도 실행 환경의 promtool은 `PROMTOOL_COMMAND`에 셸 실행 없는 명령 인자 문자열로 지정할 수 있습니다.

배포 후 갱신·백업·실패 대응은 [운영 안내](04-operations.md)를 따릅니다.
