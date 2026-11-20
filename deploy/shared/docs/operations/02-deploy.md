# 배포 준비와 검증

[공통 안내](../README.md) · 이전: [서버 파일 받기](01-checkout.md) · 다음: [운영](03-operations.md)

배포 절차의 원본은 [배포 가이드](../../../README.md)와 각 앱 가이드(`deploy/<app>/README.md`)입니다.
이 문서는 그 절차에 없는 준비 확인과, 사람이 직접 하는 접속·기능 검증을 다룹니다.

- [배포 준비](#배포-준비)
- [접속·기능 검증](#접속기능-검증)

## 배포 준비

앱별 준비물은 각 앱 가이드의 `사람이 하는 일`과 `입력`에 있고, 배포 전 검사는 [공통 시작](../../../README.md#모든-작업-공통-시작)의 `make ops-preflight`가 수행합니다. 아래는 그 밖의 확인입니다.

### 대상 context 확인

[조회] 배포할 커밋·context·노드가 맞는지 확인합니다. 서버 기본 context 값은 [운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)에 있습니다.

```bash
git rev-parse HEAD
kubectl config get-contexts
kubectl --context "<context>" get nodes -o wide
```

### 저장소 원본만 검사

[검사] 클러스터에 접속하지 않고 앱 또는 그룹의 env 형식과 Kubernetes 원본만 검사합니다. `APP`에는 [apps.json](../../apps.json)의 앱·그룹 이름을 쓰고 PROFILE은 `prod`뿐입니다.

```bash
make server-check APP=platform PROFILE=prod
```

성공: 앱마다 `서버 원본 검사 통과`. Airflow·Monitoring·Headlamp는 Helm과 고정 chart가 있어야 합니다.
개발 PC 전용인 `make env-profile-key-check`(인자 없음)와 `make k8s-render`는 local 입력까지 검사하므로 서버에서는 쓰지 않습니다.

### 외부 env를 쓰는 경우

저장소 밖의 env 파일은 앱 도구의 경로 인자로 지정하며 `source`로 실행하지 않습니다. 검사·배포·대조에 같은 경로를 붙입니다.
작성과 검사는 [환경설정](../configuration/environment.md)을 따릅니다.

```bash
make ops-preflight APP=airflow PROFILE=prod KUBE_CONTEXT="<context>" AIRFLOW_ENV=/appdata/etchax-config/airflow/k8s.env
```

- 변수 이름은 [apps.json](../../apps.json)의 `env.variable`입니다. Portal은 `PROD_API_ENV_FILE`·`PROD_WEB_ENV_FILE`, 따로 반입한 Helm chart는 `<APP>_CHART_FILE`입니다.
- 기존 DB에 연결할 때는 기존 credential과 맞춥니다. Keycloak 관리자·DB·사내 OIDC·Portal client 입력은 서로 다릅니다.

### VIP와 진입점

APP VIP의 LB backend·상태 검사·TLS 종료 위치와 Worker의 80/443 충돌은 [VIP 안내](../ingress/setup.md)로 확인합니다. 공용 Traefik의 검사·적용은 [배포 가이드](../../../README.md#공용-traefik-검사갱신)에 있습니다.

## 접속·기능 검증

`make <app>-smoke KUBE_CONTEXT="<context>"`가 워크로드 Ready, Ingress host별 HTTPS 응답, hostPort 연결을 조회 전용으로 확인합니다.
DNS 등록 전에는 `SMOKE_CONNECT=<APP VIP 주소>`로 접속 주소를 지정합니다. 인증서는 시스템 신뢰 목록과 `deploy/shared/certs/ca`의 사내 CA로 검증하며 다른 CA 파일은 `SMOKE_CA_FILE`로 더합니다.
FTP passive 포트처럼 요청이 있을 때만 열리는 hostPort는 `apps.json`의 `smoke.hostPorts`에서 제외합니다.

smoke가 확인하지 않는 것은 아래처럼 사람이 확인합니다. 배포하지 않은 앱은 `미배포`로 기록합니다.

### 1. 경로별 HTTPS 확인

접근 가능한 PC에서 backend Worker → APP VIP → DNS 순서로 같은 도메인·경로를 확인하면 어느 구간이 막혔는지 알 수 있습니다. Portal은 `/api/v1/health/`, Airflow는 `/api/v2/monitor/health`입니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
  --resolve "<도메인>:443:<Worker 또는 VIP 주소>" "https://<도메인><health 경로>"
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> "https://<도메인><health 경로>"
```

OS가 해당 CA를 신뢰하면 `--cacert`를 생략할 수 있습니다. 인증서 검증을 건너뛰는 `-k`는 쓰지 않습니다.
성공: TLS 검증을 통과하고 health 응답이 정상입니다. Airflow는 HTTP 200 외에 DB와 scheduler가 healthy인지도 봅니다. TLS·404·503 오류는 [장애 조회](../../../README.md#장애-조회)를 따릅니다.

### 2. 실제 기능 확인

브라우저와 클라이언트로 확인합니다. 시험 데이터는 정상 삭제 절차로 정리합니다.

| 앱 | 시나리오 |
| --- | --- |
| Keycloak | HTTPS → 사내 OIDC 로그인 → realm·사용자 claim |
| Portal | 로그인 callback → API → 로그아웃, 시험 파일 업로드·다운로드 |
| Airflow | UI 로그인·health, Portal 연동 시 시험 DAG 트리거·결과 |
| Monitoring / Headlamp | Grafana 지표·target / Keycloak 로그인·그룹별 리소스 조회 |
| FTP | 노드 passive 접속·시험 파일 송수신·저장 위치 |
| Registry | 다른 노드에서 사내 빌드 이미지 pull |

### 3. 결과 기록

context·namespace, 커밋·이미지·chart 버전과 함께 정적 검사, 리소스 상태, 접속·기능 검증의 결과를 나누어 적고 미완료 항목과 다음 조치를 덧붙입니다.
비밀값은 기록하지 않으며 접근하지 못했거나 확인 대기 중인 항목은 성공으로 표시하지 않습니다. 운영값이 바뀌었으면 [인프라 정보](../infrastructure/README.md)를 갱신합니다.

**다음 단계:** [운영](03-operations.md)
