# Monitoring 서버·chart 준비

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

관리 호스트에서 도구·권한·Worker·chart를 준비합니다. Portal·Keycloak·Airflow가 없어도 설치할 수 있습니다.

## 1. 시작 전에 준비할 것

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

## 2. 고정 chart 준비

Helm chart는 설치할 Kubernetes 리소스를 묶은 패키지입니다.
이 저장소는 `kube-prometheus-stack` **91.4.0**을 사용하며, 버전과 SHA-256은 [chart.lock.json](../helm/chart.lock.json)에 고정되어 있습니다.

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

**완료 기준:** 대상 Worker와 도구·권한·고정 chart를 준비했습니다. [환경설정](02-environment.md)에서 context와 env를 선택합니다.
