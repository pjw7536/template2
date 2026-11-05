# Monitoring 설치와 운영

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)

이 문서는 **사내 Kubernetes에 모니터링을 처음 설치하는 순서**를 안내합니다.
관리 서버(CP1 등)에서 한 번 배포하면 클러스터의 노드·Pod 지표를 Grafana에서 볼 수 있습니다.
Portal·Keycloak·Airflow가 실행 중이지 않아도 설치할 수 있습니다.

처음 설치한다면 **[1. 설정](#1-서버-설정과-디스크-준비) → [2. chart](#2-고정-chart-준비) → [3. 검사](#3-원본실제-설정-검사) → [4. 계정·웹 접속](#4-namespace와-관리자-secret-준비) → [5. 배포](#5-배포와-확인)** 순서로 진행하세요.
이미 설치했다면 [갱신·운영](#갱신운영), 오류가 났다면 [문제 해결](#문제-해결)로 이동합니다.

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

## 시작 전에 준비할 것

| 위치 | 준비할 것 |
| --- | --- |
| 관리 서버 | 저장소, Python 3.10+, Helm 3.19+, kubectl, 클러스터 접속용 kubeconfig |
| Kubernetes | 버전 1.25+와 Operator CRD·ClusterRole·Job 등을 설치할 권한 |
| 지정 Worker | Ready 상태, 차단 taint 없음, 데이터 디스크·여유 공간, 사내 미러 접근 |
| 웹 접속 경로 | 기본 HTTPS 접속을 사용하면 공용 Traefik·DNS/VIP·도메인 인증서 |

준비 Job은 root 권한과 호스트 폴더 마운트(`hostPath`)를 사용합니다.
node-exporter는 호스트 네트워크(`hostNetwork`)와 `hostPath`를 사용하므로 namespace 정책에서 허용되어야 합니다.
기존 Prometheus Operator가 있는 클러스터는 먼저 기존 모니터링을 사용할 수 있는지 확인합니다.
배포 도구는 새 설치에서 기존 Operator CRD를 발견하면 중단합니다.

서버 선택 checkout이 필요하면 `bash deploy/shared/scripts/checkout-server.sh monitoring`을 사용합니다.
서버 실행에는 루트 Makefile과 `deploy/monitoring`, `deploy/shared`만 필요합니다.
외부 PC 개발은 별도 `local/monitoring` 설정을 사용하며, 아래 서버 명령은 local 파일을 읽지 않습니다.

## 1. 서버 설정과 디스크 준비

**이후 명령은 관리 서버의 저장소 루트, 같은 Bash 세션에서 실행합니다.**
먼저 접속할 클러스터와 모니터링 데이터를 저장할 Worker를 확인합니다.

```bash
kubectl config get-contexts
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -L kubernetes.io/hostname
kubectl --context "$KUBE_CONTEXT" get node khinfow01 -o wide

export MONITORING_ENV="$PWD/deploy/monitoring/env/k8s.env"
chmod 600 "$MONITORING_ENV"
vi "$MONITORING_ENV"
```

`vi`는 사용하는 편집기로 바꿔도 됩니다. 설정 파일은 [env/k8s.env](env/k8s.env)입니다.

| 설정 | 무엇을 입력하나요? |
| --- | --- |
| `NODE_NAME` | 기본값 `khinfow01`. Airflow와 함께 배포할 Worker이며 위 조회의 **kubernetes.io/hostname 값**과 Ready 상태를 확인 |
| `DATA_HOST_PATH` | 해당 Worker의 전용 데이터 경로. 신규 설치 기본값은 `/appdata/monitoring` |
| `DOCKER_REGISTRY`·`QUAY_REGISTRY`·`GHCR_REGISTRY`·`K8S_REGISTRY` | 사내 미러 경로. 저장소 기본값을 대조하고 [이미지 미러 설정](#이미지-미러-설정) 확인 |
| `IMAGE_PULL_SECRET` | 미러 인증이 필요할 때 사용할 기존 Kubernetes Secret 이름. 인증이 없으면 빈 값 |
| `INGRESS_ENABLED`·`INGRESS_HOST` | 기본값은 `true`, `etch.samsungds.net`. 이 도메인으로 웹 화면에 접속 |
| `NAMESPACE`·`GRAFANA_ADMIN_SECRET` | 기본값은 `monitoring`, `monitoring-grafana-admin`. 4절에서 이 영역과 관리자 계정을 준비 |
| `INGRESS_TLS_SECRET` | 이전 설정 호환용. 기본값인 빈 값을 유지하고 인증서는 공용 Traefik에서 관리 |

이 문서의 명령은 기본 namespace와 Secret 이름을 사용합니다. 이름을 변경하면 명령에서도 함께 바꿉니다.
다른 env 파일을 쓰려면 `MONITORING_ENV`에 그 파일의 절대 경로를 export합니다.
다음 단계의 Make 명령과 Python 명령은 같은 파일을 사용합니다.

**폴더는 배포 시 자동 생성됩니다. 수동으로 만들 필요가 없습니다.**
다만 지정 Worker의 데이터 디스크가 의도한 위치에 마운트되어 있고 여유 공간이 있는지는 먼저 확인합니다.
폴더 생성은 디스크 마운트나 데이터 이전을 수행하지 않습니다. [저장소 상세](#저장소와-폴더-자동-생성)를 참고하세요.

## 2. 고정 chart 준비

Helm chart는 설치할 Kubernetes 리소스를 묶은 패키지입니다.
이 저장소는 `kube-prometheus-stack` **91.4.0**을 사용하며, 버전과 SHA-256은 [chart.lock.json](helm/chart.lock.json)에 고정되어 있습니다.

사내 미러에 접근할 수 있는 CP1 등 관리 서버의 저장소 루트에서 실행합니다.
`fetch-chart`는 chart lock에 지정한 `proxy-raw-github.com` 미러에서 다운로드하고 SHA-256을 검증합니다.
미러의 실제 패키지 제공·다운로드 가능 여부는 CP1에서 확인해야 합니다.

```bash
python3 deploy/monitoring/scripts/manage.py fetch-chart
```

다운로드한 파일은 `deploy/monitoring/helm/vendor/kube-prometheus-stack-91.4.0.tgz`입니다.
미러에서 받을 수 없으면 외부 PC에서 같은 버전의 [공식 release 파일](https://github.com/prometheus-community/helm-charts/releases/download/kube-prometheus-stack-91.4.0/kube-prometheus-stack-91.4.0.tgz)을 받아 **관리 서버의 같은 경로에 복사**합니다.
로컬 개발 도구는 공개 GitHub 경로에서 같은 버전을 받고 동일한 SHA-256을 검증합니다.
이미 파일이 준비되어 있으면 `fetch-chart`를 생략합니다.

다른 위치에 보관했다면 관리 서버에서 경로를 지정합니다.

```bash
export MONITORING_CHART_FILE=/절대경로/kube-prometheus-stack-91.4.0.tgz
```

검사·배포는 파일의 SHA-256을 확인하며 chart를 자동 다운로드하지 않습니다.
의존 chart도 패키지에 포함되어 있으므로 서버에서 `helm dependency update`를 실행하지 않습니다.
chart 파일은 Git에 커밋하지 않습니다.

## 3. 원본·실제 설정 검사

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
실제 설치는 5절의 Helm 배포가 CRD와 webhook 초기화 순서를 관리합니다.

## 4. Namespace와 관리자 Secret 준비

### Grafana 로그인 계정 등록

Namespace는 모니터링 리소스를 모아두는 설치 영역이고, Secret은 계정 정보를 전달하는 Kubernetes 리소스입니다.
먼저 관리 서버에서 설치 영역을 준비합니다.

```bash
kubectl --context "$KUBE_CONTEXT" create namespace monitoring --dry-run=client -o yaml \
  | kubectl --context "$KUBE_CONTEXT" apply -f -
kubectl --context "$KUBE_CONTEXT" -n monitoring get secret monitoring-grafana-admin --ignore-not-found
```

`monitoring-grafana-admin`이 이미 있으면 기존 계정을 사용하고 **아래 생성 단계는 생략**합니다.
처음 설치한다면 [관리자 env 샘플](env/grafana-admin.env.example)을 Git 저장소 밖으로 복사하고 실제 계정으로 편집합니다.

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
Grafana를 [선택 설정](#선택-설정)에서 비활성화했다면 namespace만 준비하고 관리자 Secret 등록은 생략합니다.
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
처음 준비한다면 [공용 진입점 준비](../shared/ingress/README.md)에 따라 설정한 뒤 실행합니다.

```bash
read -r -p '업무 도메인 fullchain PEM 경로: ' MONITORING_TLS_CERT
read -r -p '업무 도메인 개인키 PEM 경로: ' MONITORING_TLS_KEY
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST=etch.samsungds.net \
  TLS_CERT_FILE="$MONITORING_TLS_CERT" TLS_KEY_FILE="$MONITORING_TLS_KEY"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

배포 도구는 인증서와 controller 변경 권한을 확인합니다.
설치 후 기존 VIP·다른 앱·Traefik 배치를 보존하면서 Monitoring namespace의 라우팅 권한과 감시 범위를 추가합니다.
공용 HTTPS 접속을 사용하지 않으려면 [port-forward로만 접속하기](#port-forward로만-접속하기)를 먼저 적용합니다.

## 5. 배포와 확인

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
| Grafana | 4절의 관리자 계정으로 로그인. 기본 홈인 `전체 서버 · 리소스 추세`에서 서버별 그래프와 상태 표에 지표가 표시됨 |
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

대시보드 원본은 [servers-overview.json](dashboards/servers-overview.json)입니다.
Git의 JSON을 변경하고 같은 env·context로 `make monitoring-check` → `make monitoring-up`을 실행하면
Helm의 ConfigMap과 Grafana provisioning에 반영됩니다. 별도 이미지 빌드·인터넷 템플릿 다운로드가 필요하지 않습니다.
기본 Kubernetes 대시보드도 계속 사용할 수 있습니다. 공급된 대시보드는 JSON 원본에서 관리하고,
개인 화면은 Grafana에서 복사해 편집합니다.

대시보드 공급 검증은 기존 Monitoring 회귀 검사에 포함됩니다. `promtool`이 PATH에 있으면
`python3 -m unittest discover -s deploy/monitoring/tests -p 'test_dashboard.py'`에서
실제 PromQL fixture로 사용률·중복 수집·장치 필터·수집 중단 계산까지 확인합니다.
별도 실행 환경의 promtool은 `PROMTOOL_COMMAND`에 셸 실행 없는 명령 인자 문자열로 지정할 수 있습니다.

## 갱신·운영

설정을 바꾼 뒤에는 **처음 설치할 때와 같은 env·context**로 실행합니다.
새 Bash 세션에서는 1절의 `KUBE_CONTEXT`, `MONITORING_ENV`를 다시 export합니다.

```bash
make monitoring-check
make monitoring-up
```

새 Worker는 정상 가입 후 자동으로 수집 대상에 포함되므로, Worker 추가만으로 이 명령을 반복할 필요는 없습니다.
기존 node-exporter가 호스트 포트 `9100`을 사용한다면 새 DaemonSet과 충돌하므로 기존 공용 모니터링 사용 여부를 먼저 정합니다.

| 변경할 내용 | 처리 방법 |
| --- | --- |
| 같은 chart 버전의 설정 | 위 명령으로 검사 후 재적용. `make env-check APP=monitoring`도 입력·렌더 검사에 사용 가능 |
| chart 버전 | 도구가 다른 버전의 기존 release를 발견하면 중단. CRD 호환성과 공식 upgrade 절차를 먼저 검토 |
| Worker·데이터 경로 | 기존 local PV는 일반 재배포로 위치를 변경할 수 없음. [Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전) 수행 |
| Grafana 관리자 비밀번호 | Grafana DB 생성 후에는 Secret만 바꿔도 기존 비밀번호가 변경되지 않음. Grafana에서 갱신 |
| 백업 | Grafana DB·대시보드·지표를 별도 디스크에 보관. 같은 노드의 데이터만으로 노드 장애를 복구할 수 없음 |

설치 실패 시 도구는 DB·namespace를 자동 삭제하지 않습니다.
일부만 설치됐다면 Helm release 상태와 CRD·Job·Pod를 확인하고 원인을 해결한 뒤 같은 설정으로 재실행합니다.
기존 데이터를 지키기 위해 PVC·namespace·CRD를 임의 삭제하지 않습니다.

## 문제 해결

관리 서버에서 먼저 상태와 최근 이벤트를 확인합니다.

```bash
helm --kube-context "$KUBE_CONTEXT" -n monitoring list --all
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods,pvc,jobs -o wide
kubectl --context "$KUBE_CONTEXT" -n monitoring get events --sort-by=.lastTimestamp
```

| 증상·메시지 | 확인할 내용 |
| --- | --- |
| `실제 값 필요: NODE_NAME` | env의 `replace-me-node`를 실제 hostname label로 변경 |
| `Helm chart 준비 필요` | 2절의 chart 파일 위치와 `MONITORING_CHART_FILE` 확인 |
| `chart SHA-256 불일치` | 고정 버전 패키지를 다시 준비. 임의 chart로 대체하지 않음 |
| 기존 Operator CRD·다른 chart 버전 | 기존 모니터링·release 확인. CRD를 삭제해 우회하지 않음 |
| `ImagePullBackOff`·`ErrImagePull` | 실패한 이미지의 미러 경로·태그·노드 CA·접근 권한·pull Secret 확인. BusyBox도 포함 |
| `monitoring-storage-prepare-*` 실패 | 아래 Job 로그와 Pod Events 확인. root·hostPath 허용, 디스크 마운트, 파일·심볼릭 링크 점유 확인 |
| 기존 PV 경로·노드·PVC 오류 | env를 기존 저장소 설정과 대조. 기존 PV 폴더가 사라졌으면 마운트·데이터부터 복구 |
| `Pending`·PVC 미결합 | 지정 Worker Ready·taint·자원 여유, PV/PVC 연결 상태 확인 |
| Grafana 데이터 폴더 권한 오류 | 기존 폴더의 UID/GID 확인. 자동 생성은 기존 파일 권한을 변경하지 않음 |
| 화면 접속 실패 | DNS/VIP·443 경로, 공용 Traefik·인증서·`INGRESS_HOST` 확인 |
| 새 Worker 지표 없음 | 해당 노드의 node-exporter Pod, 미러 pull, `9100` 통신과 Prometheus target 확인 |

폴더 준비 Job이 실패했다면 **출력된 실제 Job 이름**으로 확인합니다.

```bash
read -r -p '실패한 준비 Job 이름: ' MONITORING_JOB
kubectl --context "$KUBE_CONTEXT" -n monitoring describe job "$MONITORING_JOB"
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods -l "job-name=$MONITORING_JOB"
kubectl --context "$KUBE_CONTEXT" -n monitoring logs "job/$MONITORING_JOB"
```

## 저장소와 폴더 자동 생성

데이터는 `NODE_NAME` Worker의 `DATA_HOST_PATH` 아래에 저장합니다.
기본 경로는 `/appdata/monitoring`이며 **새로 생성하는 서비스 폴더**에는 아래 소유권과 권한 `0770`을 적용합니다.

| 서비스 폴더 | 소유 UID:GID | local PV 예약 용량 |
| --- | --- | ---: |
| `prometheus` | `1000:2000` | 20Gi |
| `alertmanager` | `1000:2000` | 2Gi |
| `grafana` | `472:472` | 5Gi |

local PV는 해당 노드의 폴더를 Kubernetes 데이터 볼륨으로 연결하는 방식이며 별도 StorageClass가 필요하지 않습니다.
예약 용량은 실제 디스크 할당이나 사용량 제한이 아닙니다. Prometheus 보존 기준은 7일 또는 16GB이고 WAL 등 추가 공간도 필요합니다.

기존 폴더·하위 데이터의 소유권과 권한은 보존합니다. 사용자 지정 UID/GID를 사용하면 폴더 권한도 직접 맞춥니다.
저장 경로가 일반 파일·심볼릭 링크이거나 기존 PV 폴더가 사라졌으면 중단합니다.
폴더 준비 실패 시 PV·Helm 배포로 넘어가지 않습니다.

PV의 reclaim policy는 `Retain`이며 정상 갱신 시 기존 PV·PVC·namespace를 삭제하지 않습니다.
Pod 재시작에도 데이터를 보존하지만 **지정 Worker 한 대에 저장하므로 고가용성 구성은 아닙니다.**
이전 경로 `/srv/monitoring`을 쓰던 서버는 데이터 이전이 끝나기 전까지 기존 env 경로를 유지합니다.
새 Kubernetes 설치는 기존 Compose의 지표 DB를 자동 복원하지 않습니다.

## 이미지 미러 설정

아래 네 종류의 미러를 사용합니다. 각 이미지가 실행될 노드에서 해당 미러에 접근할 수 있어야 합니다.
registry 값은 URL scheme 없이 `레지스트리/proxy경로`로 입력하며 끝에 `/`를 붙이지 않습니다.
실제 주소의 관리 원본은 [사내 저장소·미러](../shared/docs/infrastructure/repositories.md)입니다.

| env 키 | 외부 원본 | 사용하는 이미지 |
| --- | --- | --- |
| `DOCKER_REGISTRY` | docker.io | Grafana, 폴더 준비용 `library/busybox:1.37.0` |
| `QUAY_REGISTRY` | quay.io | Prometheus·Operator·Alertmanager·node-exporter·Grafana sidecar·config reloader |
| `GHCR_REGISTRY` | ghcr.io | webhook 인증서 초기화 이미지 |
| `K8S_REGISTRY` | registry.k8s.io | kube-state-metrics |

Docker Hub 미러 하나만으로는 모든 이미지를 받을 수 없습니다.
3절의 `images.txt` 전체를 확인하고, 미러에 없는 이미지·태그는 승인된 경로로 반입합니다.
`IMAGE_PULL_SECRET`에는 registry 인증 Secret의 **이름만** 입력합니다. Grafana 로그인용 Secret과는 별개입니다.

## 선택 설정

### port-forward로만 접속하기

공용 HTTPS 경로를 사용하지 않을 때는 env를 아래처럼 바꾼 뒤 3절부터 진행합니다.
이 경우 4절의 Traefik·인증서 준비는 생략하며, Grafana를 사용한다면 관리자 Secret은 여전히 필요합니다.

```dotenv
INGRESS_ENABLED=false
INGRESS_HOST=
INGRESS_TLS_SECRET=
```

설치 후 접속할 PC에서 kubeconfig를 준비하고, 같은 클러스터의 context를 지정해 실행합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-grafana 3000:80
# 다른 터미널에서 같은 context를 지정한 뒤 실행합니다.
kubectl --context "$KUBE_CONTEXT" -n monitoring port-forward svc/monitoring-prometheus 9090:9090
```

주소는 `http://localhost:3000`, `http://localhost:9090/targets`입니다. 명령을 종료하면 연결도 종료됩니다.
기본 HTTPS 모드에서는 Grafana가 공개 도메인으로 리다이렉트하므로 공용 주소로 확인합니다.

### 일부 서비스를 끄거나 Helm 설정 추가하기

환경별 추가 설정은 비밀값 없는 values 파일로 작성합니다.
Make 기본 명령에는 추가 values 옵션이 없으므로, 필요한 경우 아래 명령으로 **검사·배포에 같은 파일**을 전달합니다.

```bash
read -r -p '추가 values 파일 절대 경로: ' MONITORING_VALUES
python3 deploy/monitoring/scripts/manage.py check --env "$MONITORING_ENV" --values "$MONITORING_VALUES"
python3 deploy/monitoring/scripts/manage.py render --env "$MONITORING_ENV" \
  --values "$MONITORING_VALUES" --output deploy/monitoring/rendered
python3 deploy/monitoring/scripts/manage.py deploy --context "$KUBE_CONTEXT" \
  --env "$MONITORING_ENV" --values "$MONITORING_VALUES"
```

추가 values가 env와 기본 설정을 덮어쓸 수 있으므로 최종 리소스·이미지 목록을 확인한 뒤 배포합니다.
Prometheus를 끄려면 고정 chart가 Prometheus 전용 token Secret을 참조하지 않도록 관련 감시도 함께 끕니다.

```yaml
prometheus:
  enabled: false
kubernetesServiceMonitors:
  enabled: false
```

비활성 Grafana·Prometheus·Alertmanager는 폴더 준비·신규 PV·준비 대기 대상에서 제외합니다.
기존 PV·PVC는 삭제하지 않고, Grafana가 꺼져 있으면 관리자 Secret도 조회하지 않습니다.
최종 values에서 모든 Ingress를 끄면 Traefik controller·TLS도 조회하지 않습니다.

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
