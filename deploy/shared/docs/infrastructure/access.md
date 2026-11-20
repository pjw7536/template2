# 접근 경로

[사내 인프라 정보](README.md) · [배포 가이드](../../../README.md)

클러스터 밖 작업(다른 서버, DNS, 방화벽, 인증서 발급, 관리 API)을 **어떤 도구와 계정으로 하는지**의 관리 원본입니다.
배포 문서의 클러스터 밖 단계와 `make ops-preflight`의 `볼 곳`은 이 문서의 절을 가리킵니다.

## 사용 규칙

1. 단계가 이 문서의 절을 가리키면 그 절의 `접근 방법`으로 실행하고 `완료 확인`으로 결과를 확인합니다.
2. `접근 방법`이 `미확인`이면 `찾는 방법`의 [조회] 명령으로 사용할 수 있는 경로를 먼저 확인합니다. 확인되면 이 표의 `접근 방법`·`계정 위치`·`확인 상태`를 고친 뒤 작업을 계속합니다.
3. 경로를 찾지 못했거나 권한이 거부되면 `막히면 요청할 것` 칸의 내용만 사용자에게 요청합니다. 그 단계에 의존하지 않는 작업은 계속합니다.
4. 비밀번호·토큰·개인키 값은 쓰지 않습니다. 파일 경로, Secret 이름, 계정 이름처럼 위치만 적습니다.
5. 서버 이름과 주소는 [서버·노드](servers.md), [네트워크](network.md)가 원본입니다. 이 문서에 다시 적지 않습니다.

기록 형식은 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.

## Kubernetes API

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 관리 호스트 배포 계정의 kubeconfig로 `kubectl --context "<context>"` 실행. context 이름은 [운영 위치](operations.md#운영-파일과-데이터-위치)의 서버 기본 context |
| 계정 위치 | 관리 호스트 `$HOME/.kube/config`(권한 0600). 준비 방법은 [관리 호스트 준비](../operations/04-drift.md#관리-호스트-준비) |
| 완료 확인 | [조회] `kubectl --context "<context>" get nodes`가 노드 목록을 출력 |
| 확인 상태 | 미확인. 실제 파일 위치와 계정은 서버에서 확인 필요 |
| 막히면 요청할 것 | 관리 호스트 배포 계정의 kubeconfig 배치, 또는 API VIP 6443 접근 |

## 노드 명령 실행

제어면·Worker에서 실행하는 단계(containerd 설정, 사내 CA 신뢰, API server 설정, 저장 폴더 확인, 이미지 확인)에 씁니다.
사내 서버는 노드 사이의 SSH를 쓸 수 없습니다. 관리 호스트의 kubeconfig로 대상 노드에 일회성 Job을 띄워, 그 노드의 호스트 namespace에서 root로 명령을 실행합니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 한 줄 명령: `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command '<명령>'` |
| | 여러 줄 블록: 블록을 관리 호스트의 저장소 밖 파일에 그대로 저장한 뒤 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --script <블록 파일>` |
| | 파일 보내기: `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --copy <관리 호스트 파일>:<노드의 절대 경로>`. `--command`·`--script`와 함께 쓰면 파일을 먼저 둡니다 |
| 찾는 방법 | [조회] `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'hostname; id -u'`가 노드 이름과 `0`을 출력. `<노드>`는 `kubectl --context "<context>" get nodes`의 `NAME` |
| 계정 위치 | 관리 호스트의 kubeconfig([Kubernetes API](#kubernetes-api)). 실행 이미지와 namespace는 `deploy/shared/env/node-exec.env` |
| 완료 확인 | 출력 마지막 줄이 `노드 명령 완료: <노드>`. 명령이 실패하면 `노드 명령 실패: <노드>`와 종료 코드 1 |
| 확인 상태 | 저장소 선언. 서버에서 실행해 본 적 없음 |
| 막히면 요청할 것 | 특권 Pod가 정책으로 거부되거나 노드가 실행 이미지를 받지 못하면 그 오류, 대상 노드, 실행하려는 명령 |

- 명령은 bash로 실행하며 실패한 줄에서 멈춥니다. root로 실행하므로 문서의 명령에 붙은 `sudo`는 그대로 두어도 됩니다.
- 명령마다 새 Job입니다. 앞 명령에서 정한 변수나 현재 폴더는 다음 명령에 남지 않습니다.
- Make 타깃이 아니라 Python 스크립트를 직접 실행합니다. Make는 값의 `$`를 해석해 명령을 바꿉니다.
- `--copy`로 보내는 파일의 내용은 Job 정의에 담겼다가 10분 뒤 Job과 함께 지워집니다. 비밀값이 든 파일에는 쓰지 않습니다. 64KiB까지 보낼 수 있습니다.
- 노드를 다시 시작하거나 kubelet·containerd·API server를 재시작하는 명령은 [승인] 단계입니다. 한 번에 한 대씩 실행하고 그 노드의 `Ready`를 확인한 뒤 다음 노드로 갑니다. 재시작 중에는 조회가 잠시 실패할 수 있으며 도구가 다시 시도합니다.

## 가입 전 노드

아직 클러스터에 가입하지 않은 서버(새 제어면·Worker의 OS 준비, `kubeadm init`·`join`)에서 실행하는 단계입니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 없음. SSH를 쓸 수 없고 Kubernetes로도 닿지 않습니다 |
| 완료 확인 | [조회] 가입 뒤 `kubectl --context "<context>" get node <노드>`가 `Ready`. 이후 단계는 [노드 명령 실행](#노드-명령-실행)으로 수행 |
| 확인 상태 | 사용자 확인: 사내 서버에서 SSH 불가 |
| 막히면 요청할 것 | 그 서버에서 실행할 명령 블록을 문서의 순서대로 전달하고 실행 결과를 받음. 블록의 `<...>` 자리표시는 실제 값으로 채워 전달 |

## 관리 호스트 sudo

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 비밀번호 없는 sudo. 이미지 빌드 도구 설치(`make build-tools-install`)와 시스템 CA 등록에 사용 |
| 찾는 방법 | [조회] `sudo -n true` |
| 완료 확인 | [검사] `make build-tools-check` |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 관리 호스트 배포 계정의 sudo 권한, 또는 필요한 명령의 대리 실행 |

## DNS

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. 사내 DNS 관리 절차로 레코드를 신청. 등록할 이름과 대상 주소는 [서비스 접속 주소](services.md#서비스-접속-주소)와 [VIP와 backend](network.md#vip와-backend) |
| 찾는 방법 | [조회] `getent hosts <host>`로 현재 등록 여부 확인. 신청 도구·API가 있으면 이 표에 명령 형식을 기록 |
| 계정 위치 | 미확인 |
| 완료 확인 | [조회] `getent hosts <host>`가 APP VIP 주소를 출력하고 `make <app>-smoke KUBE_CONTEXT="<context>"`에 `DNS 미등록` 표시가 없음 |
| 확인 상태 | 미확인. DNS 운영 도구는 정해지지 않음([DNS 명명](network.md#dns-명명과-향후-구역-위임)) |
| 막히면 요청할 것 | 등록할 host 이름과 대상 주소(APP VIP)를 알려 주고 등록 요청 |

DNS가 없어도 배포는 진행합니다. smoke가 APP VIP로 서비스를 확인하고 `DNS 미등록`으로 표시합니다.

## 방화벽

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. 허용할 출발지·대상·포트는 [네트워크](network.md) 원본의 해당 절 |
| 찾는 방법 | [조회] 출발지에서 `nc -zv <대상> <포트>` 또는 `make <app>-smoke`의 tcp 줄로 현재 통과 여부 확인 |
| 계정 위치 | 미확인 |
| 완료 확인 | [조회] 허용한 출발지에서 대상 포트 연결 성공 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 출발지·대상 노드·포트 목록과 개방 요청 |

## APP VIP와 LB

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. backend 추가·상태 검사 설정은 LB 관리 경로에서 수행. 대상은 [VIP와 backend](network.md#vip와-backend) |
| 찾는 방법 | [조회] `make ingress-smoke KUBE_CONTEXT="<context>"`의 tcp 줄(각 backend 노드의 443)과 `make ops-report`의 `APP VIP 443 연결` |
| 완료 확인 | [조회] APP VIP 443 연결 성공, 공개 host의 smoke 통과 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 추가할 backend 노드와 포트(80·443), 상태 검사 방식 |

## 인증서 발급

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. 발급받은 `fullchain.crt`·`private.key`를 `deploy/shared/certs/<사이트>/`에, 사내 Root·Issuing CA를 `deploy/shared/certs/ca/`에 둠. 추출은 [인증서 추출](../certificates/extract.md) |
| 찾는 방법 | [조회] `ls -l deploy/shared/certs/*/fullchain.crt deploy/shared/certs/ca/`. 필요한 SAN은 [업무 HTTPS 인증서](network.md#업무-https-인증서) |
| 계정 위치 | 미확인. PFX 비밀번호는 문서에 쓰지 않음 |
| 완료 확인 | [검사] `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`의 `공용 TLS <host>`가 `[통과]` 또는 `[자동 준비]` |
| 확인 상태 | 미확인. 추가 신청은 [대기 작업](pending.md#1-네트워크dns인증서) |
| 막히면 요청할 것 | SAN에 필요한 host 이름과 인증서·개인키 파일 배치, 또는 PFX 파일과 비밀번호 입력 방법 |

## 파일 반입

사내 미러에서 받을 수 없는 chart·이미지·패키지를 관리 호스트나 노드로 가져올 때 씁니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 먼저 사내 미러에서 받음(`make <app>-fetch-chart`, 노드의 `crictl pull`). 미러에 없으면 반입: 방법 미확인 |
| 찾는 방법 | [조회] 미러 주소는 [저장소·미러](repositories.md). chart는 `deploy/<app>/helm/chart.lock.json`의 이름·버전·SHA-256과 대조 |
| 완료 확인 | [검사] `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`의 `chart`가 `[통과]`, 이미지는 대상 노드에서 `crictl pull <이미지>` 성공 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 필요한 파일 이름·버전·SHA-256과 둘 경로 |

## 운영 입력 파일

저장소의 기본 env를 고치지 않고 다른 값을 쓸 때의 위치입니다. 운영 agent는 저장소 파일을 수정하지 않습니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 저장소 밖 폴더에 env를 복사해 수정하고, 그 경로를 앱의 env 변수(예: `AIRFLOW_ENV=<경로>`)로 검사·배포·대조 명령에 같게 붙임. 변수 이름은 [apps.json](../../apps.json)의 `inputs` |
| 계정 위치 | [운영 위치](operations.md#운영-파일과-데이터-위치)의 `관리 호스트 외부 앱 설정` 행. 권한 0600 |
| 완료 확인 | [검사] `make <app>-check KUBE_CONTEXT="<context>" <변수>=<경로>` 통과 |
| 확인 상태 | 안내·예시. 실제 서버 경로는 처음 만들 때 운영 위치에 기록 |
| 막히면 요청할 것 | 비어 있는 키의 실제 값(키 이름만 알려 주고 값은 파일에 직접 입력받음) |

## Keycloak 관리 API

realm 설정, client·그룹·역할, 사용자 조회에 씁니다. 관리 화면에서 하는 설정도 이 API로 합니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 저장소의 Make 타깃(`keycloak-setup`, `keycloak-access-apply`, `keycloak-org-sync`, `headlamp-oidc-setup`, `airflow-keycloak-client`, `iam-check`·`iam-up`). 타깃이 없는 설정은 `python3 deploy/keycloak/scripts/admin_env.py --env <Keycloak env> -- <명령>`으로 관리자 환경변수를 받아 Admin REST API 호출 |
| 계정 위치 | Keycloak env의 `bootstrap-admin-username`·`bootstrap-admin-password`. CA는 `deploy/shared/certs/<SSO host>/keycloak-ca-bundle.pem` |
| 완료 확인 | 각 타깃의 성공 문구. dry-run이 있는 타깃은 다시 실행해 `변경 없음` 확인 |
| 확인 상태 | 저장소 선언. 서버 적용은 [대기 작업](pending.md#3-앱-배포) |
| 막히면 요청할 것 | 관리자 계정이 env와 다르면 실제 계정 정보의 위치 |

## AD FS

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. 사내 AD FS에 Keycloak용 client를 발급받고 redirect URI를 등록. 등록할 값은 [Keycloak 사전 준비](../../../keycloak/README.md#사전-준비) |
| 완료 확인 | [검사] `make keycloak-check KUBE_CONTEXT="<context>"` 통과와 `make keycloak-setup`의 IdP 사전 검사 통과 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | client ID·secret 발급과 redirect URI 등록. 받은 값은 운영 입력 파일에 직접 입력받음 |

## 외부 DB

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. Portal용 PostgreSQL의 DB·계정·`pg_trgm` extension 준비. 접속값은 Portal API env의 `DJANGO_DB_*` |
| 찾는 방법 | [조회] 관리 호스트에서 `pg_isready -h <host> -p <port>`. DB 클라이언트가 없으면 `make portal-check` 뒤 migration 사전 검사 Job의 결과로 확인 |
| 완료 확인 | [검사] `make portal-check KUBE_CONTEXT="<context>"` 통과, 배포 시 `portal-migrate` Job `Complete` |
| 확인 상태 | 미확인. Portal 운영 DB의 위치는 [서비스·업무 연동](services.md) |
| 막히면 요청할 것 | DB host·port·DB 이름·계정과 `pg_trgm` 설치 여부 |

## 화면 기능 확인

브라우저 로그인, 관리 화면 조작, 파일 송수신처럼 smoke가 확인하지 않는 기능입니다.

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 관리 호스트에서 `curl`로 확인할 수 있는 범위(HTTPS 응답, 로그인 화면으로의 이동, OIDC discovery, FTP 송수신)를 먼저 확인. 시나리오는 [접속·기능 검증](../operations/02-deploy.md#접속기능-검증) |
| 찾는 방법 | 실제 브라우저 세션을 쓸 수 있는지는 미확인 |
| 완료 확인 | 시나리오 표의 항목별 결과를 [결과 기록](../operations/02-deploy.md#3-결과-기록)에 남김 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 확인하지 못한 시나리오 이름과 접속 주소. 사용자가 브라우저로 확인한 결과를 받음 |

## 보고서 전달

| 항목 | 내용 |
| --- | --- |
| 접근 방법 | 미확인. `make ops-report`가 만든 별칭 보고서 파일을 외부 개발 환경으로 옮김 |
| 완료 확인 | 전달한 파일이 [서버 상태 보고](../operations/04-drift.md#서버-상태-보고)의 검사(주소·서버명 없음)를 통과 |
| 확인 상태 | 미확인 |
| 막히면 요청할 것 | 보고서 파일 경로를 알려 주고 전달 요청 |
