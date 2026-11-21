# 배포 준비와 검증

[공통 안내](../README.md) · 이전: [서버 파일 받기](01-checkout.md) · 다음: [운영](03-operations.md)

배포 절차의 원본은 [배포 가이드](../../../README.md)와 각 앱 가이드(`deploy/<app>/README.md`)입니다.
이 문서는 그 절차에 없는 준비 확인과 접속·기능 검증을 다룹니다.

- [배포 준비](#배포-준비)
- [접속·기능 검증](#접속기능-검증)

## 배포 준비

앱별 준비물은 각 앱 가이드의 `사전 준비`와 `입력`에 있습니다. 배포 전 검사는 `make ops-deploy`가 첫 단계인 준비 검사로 수행하고, 배포 없이 준비 상태만 볼 때는 [설치 준비 점검](../../../README.md#설치-준비-점검)을 씁니다. 아래는 그 절차를 보충하는 확인입니다.

### 대상 context 확인

[조회] 배포할 커밋·context·노드가 맞는지 확인합니다. 서버 기본 context 값은 [운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)에 있습니다.

```bash
git rev-parse HEAD
kubectl config get-contexts
kubectl --context "<context>" get nodes -o wide
```

### 준비 검사 출력 읽기

[검사] 앱 하나의 준비 상태를 조회합니다. 클러스터를 바꾸지 않습니다.

```bash
make ops-preflight APP=<app> KUBE_CONTEXT="<context>"
```

항목마다 한 줄이 나오고 줄의 형식은 `[표시] 항목 — 설명`입니다. 해결할 것이 있는 줄에는 `명령: …`과 `볼 곳: …`이 붙습니다.
자동화에서 `PREFLIGHT_JSON=1`을 주면 표준 출력으로 검사 결과 JSON을 읽을 수 있습니다. 자동 준비 진행 메시지는 표준 오류에 표시됩니다.

| 줄의 시작 | 뜻 | 할 일 |
| --- | --- | --- |
| `[통과]` | 준비됨 | 없음 |
| `[자동 준비]` | 저장소 도구로 준비할 수 있음. `명령:`이 그 명령 | `make ops-deploy`가 준비 검사에서 실행합니다. 배포 없이 준비만 하려면 같은 명령에 `PREFLIGHT_PREPARE=1`을 붙입니다([변경]) |
| `[배포 차단]` | 저장소 도구로 해결할 수 없음 | `볼 곳:`이 가리키는 [접근 경로](../infrastructure/access.md) 절의 방법으로 해결한 뒤 다시 실행. `명령:`이 `make ops-deploy APP=<다른 앱>`이면 그 앱을 먼저 배포 |
| `[안내]` | 배포를 막지 않는 남은 일(DNS 등록 등) | 배포는 진행하고 `볼 곳:`의 절로 수행 |

| 항목 | 확인하는 것 |
| --- | --- |
| `클러스터 접속` | API 접속과 노드 조회. 실패하면 클러스터가 필요한 항목은 건너뜁니다 |
| `저장소 원본` | 배포 정의의 정적 검사. 실패하면 저장소 수정이 필요하므로 그 줄을 보고합니다 |
| `먼저 필요한 앱 <app>` | [apps.json](../../apps.json)의 `dependsOn` 앱의 워크로드가 있는지 |
| `입력 <변수>` | 입력 파일이 있는지. 내용은 `앱 검사`가 봅니다 |
| `chart` | Helm 앱의 고정 chart 파일. 없으면 `make <app>-fetch-chart`가 자동 준비 |
| `사내 CA 묶음` | Keycloak OIDC를 검증하는 앱의 CA 묶음. CA 파일이 있으면 `make ca-bundle`이 자동 준비 |
| `이미지 빌드 도구` | 이미지를 빌드하는 앱의 nerdctl·BuildKit. 없으면 `make build-tools-install`이 자동 준비 |
| `공용 TLS <host>` | 공개 host의 인증서 등록. `deploy/shared/certs/<사이트>/`에 맞는 인증서가 있으면 `make ingress-tls-up`이 자동 준비 |
| `DNS <host>` | 관리 호스트에서 host가 조회되는지. 없으면 `[안내]` |
| `앱 검사` | `make <app>-check`의 결과. 위 항목에 남은 것이 있으면 실행하지 않고 `[안내]`로 표시 |

마지막 줄은 `준비 검사 결과: 배포 가능 (<app>)` 또는 `준비 검사 결과: 남은 항목 <n>건 (<app>)`입니다. 남은 항목은 `[자동 준비]`와 `[배포 차단]`의 수이며 `[안내]`는 세지 않습니다.
`make ops-deploy`에서는 같은 내용이 요약 JSON의 `blocked`(해결하지 못한 항목)와 `pending`(`[안내]`)으로 나옵니다.

### 저장소 원본만 검사

[검사] 클러스터에 접속하지 않고 앱 또는 그룹의 env 형식과 Kubernetes 원본만 검사합니다. `APP`에는 [apps.json](../../apps.json)의 앱·그룹 이름을 씁니다.

```bash
make server-check APP=platform
```

성공: 앱마다 `서버 원본 검사 통과: <app>`. Airflow·Monitoring·Headlamp는 Helm과 고정 chart가 있어야 합니다.
개발 PC 전용인 `make env-profile-key-check`(인자 없음)와 `make k8s-render`는 local 입력까지 검사하므로 서버에서는 쓰지 않습니다.

### 외부 env를 쓰는 경우

저장소의 기본 env와 다른 값이 필요하면 저장소 파일을 고치지 않고 저장소 밖에 복사한 env를 씁니다. 위치와 방법은 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)에 있습니다.
외부 env 경로는 앱의 env 변수로 지정하며 `source`로 실행하지 않습니다. 검사·배포·대조·진단의 각 명령에 같은 값을 붙입니다. 작성 형식과 키는 [환경설정](../configuration/environment.md)을 따릅니다.

[검사] 예: Airflow의 외부 env로 준비 검사를 실행합니다.

```bash
make ops-preflight APP=airflow KUBE_CONTEXT="<context>" AIRFLOW_ENV=/appdata/etchax-config/airflow/k8s.env
```

- 변수 이름은 [apps.json](../../apps.json)의 `inputs[].variable`이며 각 앱 가이드의 `입력` 표에도 있습니다. Portal은 `PROD_API_ENV_FILE`·`PROD_WEB_ENV_FILE`, 따로 반입한 Helm chart는 `<APP>_CHART_FILE`입니다.
- 기존 DB에 연결할 때는 기존 credential과 맞춥니다. Keycloak 관리자·DB·사내 OIDC·Portal client 입력은 서로 다릅니다.

### 공용 인증 입력 준비

프로젝트 루트의 Git 추적 파일 `identity.env`에는 `CORP_OIDC_CLIENT_ID`와 `IAM_PLATFORM_ADMIN_USERNAMES`를 `KEY=값` 형식으로 입력합니다. 관리자 목록은 기존 계정의 EPID를 쉼표로 구분해 적습니다. 이 키가 없으면 IAM 원본의 목록을 사용하고, 빈 값이면 새 관리자를 추가하지 않습니다.

같은 폴더에 권한 `0600`으로 `identity.env.local`을 만들고 `CORP_OIDC_CLIENT_SECRET`을 입력합니다. 기존 외부 인증 env를 사용하는 환경은 `IDENTITY_ENV`에 파일 경로를 지정하며, 그 파일에는 세 키를 함께 둘 수 있습니다.

[변경] 기존에 쓰던 두 앱 env를 원본으로 지정합니다. 이미 배포한 Keycloak에서는 현재 DB·관리자 값과 맞는 기존 env를 사용합니다. 둘 중 하나가 저장소 기본 env를 사용한다면 해당 인자를 생략합니다.

```bash
make identity-env-prepare KEYCLOAK_ENV="<기존 Keycloak env 경로>" IAM_ENV="<기존 IAM env 경로>"
```

성공하면 `identity.env` 옆 `identity.env.generated/`에 권한 `0600`으로 두 파일을 만들고 `KEYCLOAK_ENV=…`와 `IAM_ENV=…` 경로를 출력합니다. `identity.env.local`과 생성 디렉터리는 Git에서 제외합니다. 실패하면 표시한 키의 입력과 파일 권한을 확인한 뒤 같은 명령을 다시 실행합니다.

Keycloak에는 생성한 `KEYCLOAK_ENV`를, Etch Members에는 생성한 두 경로를 검사·배포·대조 명령에 전달합니다. 앱 가이드의 명령에서 env 경로만 바꾸면 됩니다. 운영 입력이나 원본 env를 갱신한 뒤 다시 생성하며, 생성본은 배포 입력으로 사용합니다. 출력된 경로만 기록하고 값은 출력하지 않습니다.

### VIP와 진입점

공용 Traefik의 설치·갱신·확인은 [ingress 가이드](../../ingress/README.md)에 있습니다. APP VIP의 LB backend·상태 검사·TLS 종료 위치와 Worker의 80/443 충돌은 [Traefik 셋업](../ingress/setup.md)으로 확인하고, LB 작업은 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법으로 합니다.

## 접속·기능 검증

`make <app>-smoke KUBE_CONTEXT="<context>"`가 워크로드 Ready, Ingress host별 HTTPS 응답, hostPort 연결을 조회 전용으로 확인합니다.

- DNS에 없는 host는 [별칭 표](../infrastructure/aliases.json)의 APP VIP로 자동으로 다시 접속합니다. 서비스가 응답하면 그 줄을 `DNS 미등록. APP VIP 직접 접속: …`으로 통과시키고 마지막 줄이 `smoke 통과: <app> (DNS 미등록 host N개)`가 됩니다. 이때 배포는 끝난 것이며 DNS 등록은 [DNS](../infrastructure/access.md#dns) 절의 방법으로 하는 남은 일입니다.
- `DNS 조회 실패, APP VIP 직접 접속도 실패: …`는 서비스 자체에 닿지 않는 것입니다. [장애 조회](../../../README.md#장애-조회)를 따릅니다.
- 인증서는 시스템 신뢰 목록과 `deploy/shared/certs/ca`의 사내 CA로 검증하며 다른 CA 파일은 `SMOKE_CA_FILE=<경로>`로 더합니다.
- 접속할 주소를 직접 정해야 할 때만(예: 특정 Worker 확인) 선택 입력 `SMOKE_CONNECT=<주소>`를 붙입니다.
- FTP passive 포트처럼 요청이 있을 때만 열리는 hostPort는 `apps.json`의 `smoke.hostPorts`에서 제외합니다.

smoke가 확인하지 않는 기능은 아래 시나리오로 확인합니다. 확인 방법은 [화면 기능 확인](../infrastructure/access.md#화면-기능-확인) 절에 있습니다. 배포하지 않은 앱은 `미배포`로 기록합니다.

### 1. 경로별 HTTPS 확인

[조회] 관리 호스트에서 backend Worker → APP VIP → DNS 순서로 같은 도메인·경로를 확인하면 어느 구간이 막혔는지 알 수 있습니다. Portal은 `/api/v1/health/`, Airflow는 `/api/v2/monitor/health`, IAM은 `/api/workload/healthz`입니다. `<CA PEM 파일>`은 [사내 CA 묶음](../../../README.md#사내-ca-묶음)의 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`입니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
  --resolve "<도메인>:443:<Worker 또는 VIP 주소>" "https://<도메인><health 경로>"
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> "https://<도메인><health 경로>"
```

OS가 해당 CA를 신뢰하면 `--cacert`를 생략할 수 있습니다. 인증서 검증을 건너뛰는 `-k`는 쓰지 않습니다.
성공: TLS 검증을 통과하고 health 응답이 정상입니다. Airflow는 HTTP 200 외에 DB와 scheduler가 healthy인지도 봅니다. TLS·404·503 오류는 [장애 조회](../../../README.md#장애-조회)를 따릅니다.

### 2. 실제 기능 확인

[화면 기능 확인](../infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다. 관리 호스트에서 `curl`로 볼 수 있는 범위(HTTPS 응답, 로그인 화면으로의 이동, OIDC discovery, FTP 송수신)를 먼저 확인하고, 브라우저가 필요한 항목은 그 절의 `막히면 요청할 것`을 따릅니다. 시험 데이터는 정상 삭제 절차로 정리합니다.

| 앱 | 시나리오 |
| --- | --- |
| Keycloak | HTTPS → 사내 OIDC 로그인 → realm·사용자 claim |
| IAM | HTTPS → 플랫폼 관리자 로그인 → 권한 화면과 업무 부하 월별 조회 |
| Portal | 로그인 callback → API → 로그아웃, 시험 파일 업로드·다운로드 |
| Airflow | UI 로그인·health, Portal 연동 시 시험 DAG 트리거·결과 |
| Monitoring / Headlamp | Grafana 지표·target / Keycloak 로그인·그룹별 리소스 조회 |
| FTP | 노드 passive 접속·시험 파일 송수신·저장 위치 |
| Registry | 관리 워커에서 시험 이미지 push, 대상 워커 각각의 [CRI pull](../../../registry/docs/01-operations.md#수동-pushpull-시험) |

### 3. 결과 기록

context·namespace, 커밋·이미지·chart 버전과 함께 정적 검사, 리소스 상태, 접속·기능 검증의 결과를 나누어 적고 미완료 항목과 다음 조치를 덧붙입니다.
실행 결과는 [운영 기록](01-checkout.md#운영-기록)을 권장합니다. 공유할 운영값은 [인프라 원본](../infrastructure/README.md#기록-규칙)에 반영할 수 있습니다. 비밀값은 기록하지 않으며 접근하지 못했거나 확인 대기 중인 항목은 성공으로 표시하지 않습니다.

**다음 단계:** [운영](03-operations.md)
