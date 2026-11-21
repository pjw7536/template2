# Keycloak 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

사내 인증 서버(Keycloak)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 사내 AD FS 로그인을 중계하는 인증 서버. Portal·Headlamp·Airflow가 각자 전용 client로 realm `etch`에 연결 |
| namespace | `etch-sso` (공용 Traefik과 같은 namespace) |
| 실행 Worker | `khplane01w09`, DB 데이터 `/appdata/keycloak-postgres`(없으면 `keycloak-up`이 생성) |
| 공개 주소 | `https://sso.etch.samsungds.net`, realm `etch`, 사내 IdP alias `oidc` |
| 배포 명령 | `make ops-deploy APP=keycloak` = 준비 검사 → `keycloak-check` → `keycloak-up` → `keycloak-setup` → `keycloak-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, discovery issuer가 `https://sso.etch.samsungds.net/realms/etch` |
| 먼저 필요한 것 | 앱 `ingress`(공용 Traefik), `sso.etch.samsungds.net`의 인증서 파일, 사내 AD FS client 값이 env에 있음 |

## 구성

- 서버: Keycloak 26.7.1과 전용 PostgreSQL 16을 각각 단일 replica로 실행합니다.
- 저장: 지정 Worker 한 대의 정적 local PV 50Gi(`Retain`)입니다. 단일 Worker의 로컬 디스크에 의존하므로 HA가 아니며 PostgreSQL 외부 백업을 별도로 준비합니다.
- 접속: DNS → APP VIP → 공용 Traefik(Worker host port 80/443에서 TLS 종료) → Keycloak입니다. 인증서는 공용 `etch-sso/traefik-tls`에 등록합니다. 공용 Traefik은 앱 [ingress](../shared/ingress/README.md)가 배포하며, `keycloak-up`은 Traefik이 있고 공용 TLS를 읽는지만 확인하며 Traefik을 설치·갱신하지 않습니다.
- 로그인: 사내 AD FS에서 발급받은 client로 사내 IdP(`oidc`)에 연결합니다. 사내 claim은 IdP mapper가 사용자 필드로 받고 앱별 mapper가 토큰으로 발급합니다([사용자 필드와 claim](docs/02-configure.md#사용자-필드와-claim)).
- 설정: `keycloak-setup`이 realm → 사내 IdP → 사용자 프로필 → EPID username 정책과 IdP mapper를 Job으로 반영합니다. CSV 경로가 있으면 소속 그룹·사용자와 소속별 역할을 이어서 등록합니다. [IAM 배포](../iam/README.md#a-최초-설치)는 앱 client가 준비된 뒤 IAM 관리자 정책과 앱 역할을 반영합니다.
- 앱 연결: 앱 client는 각 앱의 배포가 등록합니다([앱 연결](docs/02-configure.md#앱-연결)). 최초 설치에는 Portal client secret이 필요하지 않습니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 앱 `ingress`(공용 Traefik) 배포([ingress 가이드](../shared/ingress/README.md)) | `make ops-preflight APP=keycloak KUBE_CONTEXT="<context>"`의 `먼저 필요한 앱 ingress`가 `[통과]` |
| `sso.etch.samsungds.net`을 SAN에 가진 `fullchain.crt`·`private.key`를 `deploy/shared/certs/sso.etch.samsungds.net/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급), [파일 기준](docs/01-prepare.md#tlsca-준비)). 공용 TLS 등록은 `ops-deploy`의 준비 검사가 자동으로 수행 | `make ops-preflight APP=keycloak KUBE_CONTEXT="<context>"`의 `공용 TLS sso.etch.samsungds.net`이 `[통과]` 또는 `[자동 준비]` |
| 사내 AD FS client 발급과 redirect URI `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint` 등록([AD FS](../shared/docs/infrastructure/access.md#ad-fs)), 발급값을 Keycloak env의 `CORP_OIDC_CLIENT_ID`·`CORP_OIDC_CLIENT_SECRET`에 반영([입력 키](docs/01-prepare.md#사내-identity-provider용-값)) | `make keycloak-oidc-check KUBE_CONTEXT="<context>"`가 `사전 검사 통과` |
| Worker `khplane01w09`의 `/appdata`가 데이터 디스크에 마운트되고 50Gi 이상 여유 | [Worker 디스크 확인](docs/01-prepare.md#worker-디스크-확인) |
| DNS `sso.etch.samsungds.net` → APP VIP 등록([DNS](../shared/docs/infrastructure/access.md#dns)) | `getent hosts sso.etch.samsungds.net` |

DNS가 아직 없어도 배포는 진행합니다. smoke가 APP VIP로 서비스를 확인해 `DNS 미등록`으로 표시하고, 등록은 `ops-deploy` 요약의 `pending`에 남습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `KEYCLOAK_ENV` | Keycloak env 경로 | `deploy/keycloak/env/prod.env`. 다른 값을 쓰면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 경로를 모든 명령에 같게 붙임 |
| `KEYCLOAK_SDWTS_CSV`, `KEYCLOAK_USERS_CSV` | 배포에서 사전 등록할 소속·사용자 [CSV 경로](docs/02-configure.md#1-입력-파일-검사). 사용자 CSV를 쓰려면 소속 CSV도 지정 | 비움. 소속 CSV만 주면 그룹·소속별 역할만 등록 |
| 관리자 계정 | 관리 API 도구(SDWT·소속·앱 역할)의 로그인 | Make가 env의 `bootstrap-admin-username`·`bootstrap-admin-password`를 자동 전달([Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)) |

공용 Traefik의 배치(`VIP_BACKENDS`)는 Keycloak의 입력이 아니며 [ingress 가이드](../shared/ingress/README.md#입력)에서 다룹니다.

사내 SSO 발급값과 Etch Members 관리자 목록을 `identity.env`에서 관리한다면 [공용 인증 입력 준비](../shared/docs/operations/02-deploy.md#공용-인증-입력-준비)에서 생성한 `KEYCLOAK_ENV`를 사용합니다.

env 파일의 키입니다. 형식과 Discovery 해석은 [환경설정](docs/01-prepare.md#환경설정)에 있습니다.

| 키 | 의미 |
| --- | --- |
| `postgres-password` | 새 Keycloak PostgreSQL의 비밀번호 |
| `bootstrap-admin-username`, `bootstrap-admin-password` | 최초 관리자 계정. 설정 Job과 관리 API 도구도 같은 계정 사용 |
| `keycloak-public-url` | 공개 HTTPS URL. 경로와 끝의 `/` 없음 |
| `CORP_OIDC_DISCOVERY_URL` | 사내 metadata URL |
| `CORP_OIDC_CLIENT_ID`, `CORP_OIDC_CLIENT_SECRET` | 사내 AD FS에서 발급받은 client |
| `CORP_OIDC_CLIENT_AUTH_METHOD`, `CORP_OIDC_VALIDATE_SIGNATURE` | `client_secret_post`, `true` |

## A. 최초 설치

1. [검사] 준비 검사로 먼저 필요한 앱 `ingress`와 입력을 확인합니다.
   ```bash
   make ops-preflight APP=keycloak KUBE_CONTEXT="<context>"
   ```
   성공: `[배포 차단]`으로 시작하는 줄이 없습니다. `[자동 준비]` 줄(공용 TLS 등록)은 2번에서 자동으로 실행됩니다.
   - `[배포 차단] 먼저 필요한 앱 ingress`: [ingress 가이드](../shared/ingress/README.md)의 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`를 먼저 실행하고 이 검사를 다시 실행합니다.
   - `[배포 차단] 공용 TLS sso.etch.samsungds.net`: 인증서 파일이 없는 것입니다. [사전 준비](#사전-준비)의 둘째 행을 수행합니다.
   - 그 밖의 `[배포 차단]`: 그 줄의 `볼 곳`에 적힌 [접근 경로](../shared/docs/infrastructure/access.md) 절로 해결합니다.

   준비 검사는 AD FS client 값을 보지 않습니다. [사전 준비](#사전-준비)의 AD FS 행이 미완료면 2번이 `keycloak-setup`에서 `설정 중단: 필수 설정 누락`으로 끝나므로 그 행을 먼저 완료합니다.
2. [변경] 배포와 설정. 준비 검사(공용 TLS 자동 등록), DB 폴더 준비, 스택 적용, realm·사내 IdP·사용자 프로필·EPID username 정책·IdP mapper 반영(각 Job 최대 15분), 입력한 CSV 등록, smoke, 대조를 순서대로 수행합니다.
   ```bash
   make ops-deploy APP=keycloak KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 단계별 출력은 `Keycloak 입력·원본·기존 Secret·worker 검사 통과. 클러스터를 변경하지 않았습니다.` → `Keycloak 배포 완료: https://sso.etch.samsungds.net` → `설정 완료: mappers` → `smoke 통과: keycloak` 순서입니다.
   - `failedStep`이 `preflight`면 JSON의 `blocked`를 1번과 같은 방법으로 해결하고 같은 명령을 다시 실행합니다.
   - `failedStep`이 `keycloak-setup`이면 [문제 해결](#문제-해결과-멈춤-조건)의 Job 로그 조회를 따릅니다.
   - `pending`에 `DNS sso.etch.samsungds.net`이 있으면 배포는 끝난 것입니다. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

소속·사용자 CSV를 배포에 포함하려면 [입력](#입력)의 경로를 위 명령에 Make 변수로 전달합니다. 관리 호스트에서 [Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)에 접속할 수 있어야 하며 `소속별 역할 반영 완료` 출력으로 확인합니다. CSV나 관리 API 오류로 `keycloak-setup`이 실패하면 오류를 해결한 뒤 같은 입력으로 다시 배포합니다.

앱별 client와 Headlamp 관리 그룹은 [앱 배포](docs/02-configure.md#앱-연결)에서 적용합니다. IAM 권한과 앱 역할은 필요한 앱 client가 모두 등록된 뒤 [IAM 배포](../iam/README.md#a-최초-설치)로 반영합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| manifest·이미지 태그·realm·IdP·프로필·mapper 설정, env의 `CORP_OIDC_*` | [변경] `make ops-deploy APP=keycloak KUBE_CONTEXT="<context>"` |
| 인증서 갱신 | [변경] 새 파일을 `deploy/shared/certs/sso.etch.samsungds.net/`에 둔 뒤 [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=sso.etch.samsungds.net`으로 실행. 성공: `공용 TLS 등록 완료: sso.etch.samsungds.net` |
| `deploy/keycloak/access/catalog.json` | [변경] [선택 절](#선택-sdwt-소속역할-관리-api)의 4·5단계 |
| SDWT·사용자 CSV | [변경] CSV 경로를 전달해서 A의 배포를 실행하거나 [선택 절](#선택-sdwt-소속역할-관리-api)의 1~3단계 실행 |
| env의 `postgres-password`·`bootstrap-admin-username`·`bootstrap-admin-password` | [검사] `make keycloak-check KUBE_CONTEXT="<context>"`. env만 바꿔서는 실제 DB·관리자 비밀번호가 바뀌지 않고 검사가 `keycloak-runtime: 기존 Secret과 입력이 다릅니다`로 끝납니다. [기존 Secret과 env가 다른 경우](docs/03-operations.md#기존-secret과-env가-다른-경우)를 따릅니다 |
| 공개 주소 변경 | [승인] 로그인이 재시작되고 모든 앱의 issuer가 바뀝니다. 새 주소와 영향받는 앱을 보여 주고 승인받은 뒤 [공개 인증 주소 변경](docs/03-operations.md#공개-인증-주소-변경) |

### 선택: SDWT 소속·역할 (관리 API)

SDWT 소속·사용자나 역할만 개별 적용할 때 사용합니다. `keycloak-setup`이 끝난 뒤에 실행합니다. Keycloak 관리 API를 쓰므로 `KUBE_CONTEXT`가 필요 없고, 관리자 계정은 Make가 env에서 자동으로 넘깁니다([Keycloak 관리 API](../shared/docs/infrastructure/access.md#keycloak-관리-api)).
CSV의 내용은 요청으로 받은 소속 데이터만 씁니다. 파일로 받았으면 그 경로를 쓰고, 목록으로 받았으면 [입력 파일 작성](docs/02-configure.md#1-입력-파일-검사)에 따라 저장소 밖에 CSV로 만듭니다. 요청에 소속 데이터가 없으면 1~3단계를 실행하지 않습니다.

| 순서 | 구분 | 명령 | 성공 |
| --- | --- | --- | --- |
| 1 | [검사] CSV만 검사 | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1` | `CSV 검증 완료: SDWT <n>개, 사용자 <n>명 (서버 연결 없음)` |
| 2 | [조회] dry-run | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0` | `계획:` 줄들과 `dry-run 완료` |
| 3 | [변경] 적용 | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0` | `적용 완료`와 `소속별 역할 반영 완료` |
| 4 | [조회]→[변경] 소속별 역할 | `make keycloak-org-sync` → `make keycloak-org-sync KEYCLOAK_ORG_APPLY=1` | 다시 실행한 `make keycloak-org-sync`가 `계획: 변경 없음` |
| 5 | [조회]→[변경] 앱 역할 | `make keycloak-access-apply` → `make keycloak-access-apply KEYCLOAK_ACCESS_APPLY=1` | 다시 실행한 `make keycloak-access-apply`가 `계획: 변경 없음` |

- 4·5단계의 `경고:` 줄은 적용을 막지 않습니다. 도구는 트리나 카탈로그에 없는 역할을 지우지 않고 알리기만 합니다. 경고 줄을 보고에 남기고, 경고에 나온 역할을 직접 지우지 않습니다. `client '<이름>'가 없어 건너뜁니다`는 그 앱을 배포한 뒤 5단계를 다시 실행하면 사라집니다.
- 사용자 CSV가 없으면 `KEYCLOAK_USERS_CSV=`로 비워 실행하며 이때는 그룹 설정만 수행합니다.
- CSV 형식과 각 단계의 결과는 [SDWT 그룹·사용자](docs/02-configure.md#sdwt-그룹사용자), [소속별 역할](docs/02-configure.md#소속별-역할), [앱 역할](docs/02-configure.md#앱-역할)에 있습니다.

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" get pv keycloak-postgres-data
kubectl --context "<context>" -n etch-sso get pvc keycloak-postgres-data
kubectl --context "<context>" -n etch-sso get pods -o wide
make keycloak-smoke KUBE_CONTEXT="<context>"
```

성공: PV·PVC `Bound`, keycloak·postgres Pod Running, `smoke 통과: keycloak`. 뒤에 `(DNS 미등록 host 1개)`가 붙으면 서비스는 정상이고 DNS 등록만 남은 것이므로 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.

discovery의 issuer와 사내 로그인은 [설정 완료 확인](docs/02-configure.md#설정-완료-확인)으로 확인합니다.

## 문제 해결과 멈춤 조건

[조회] `keycloak-setup`이 실패하면 Job 로그를 확인합니다. Job 이름: `keycloak-realm-setup`, `keycloak-oidc-setup`, `keycloak-user-profile-setup`, `keycloak-idp-mappers-setup`.

```bash
kubectl --context "<context>" -n etch-sso get jobs
kubectl --context "<context>" -n etch-sso logs job/<실패한 Job 이름>
```

원인을 해결한 뒤 [변경] `make keycloak-setup KUBE_CONTEXT="<context>"`를 같은 입력으로 다시 실행합니다. `설정 완료: mappers`와 CSV를 준 경우의 `소속별 역할 반영 완료`를 확인합니다.

서버 기동이 실패하면 [조회]로 이벤트와 로그를 확인합니다. 그 밖의 증상은 [장애 조회](../README.md#장애-조회)를 따릅니다.

```bash
kubectl --context "<context>" -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n etch-sso logs statefulset/keycloak-postgres
kubectl --context "<context>" -n etch-sso logs deployment/keycloak
kubectl --context "<context>" -n etch-sso logs deployment/traefik
```

| 증상 | 원인과 조치 |
| --- | --- |
| smoke `DNS 미등록. APP VIP 직접 접속: …` | 서비스는 정상이고 smoke도 통과. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 `sso.etch.samsungds.net`을 등록 |
| smoke `DNS 조회 실패, APP VIP 직접 접속도 실패: …` | DNS와 무관하게 서비스에 닿지 않음. 위 [조회]로 Traefik·Keycloak Pod를 확인하고 [장애 조회](../README.md#장애-조회)의 404 / 503·TLS 오류 행을 따름 |
| `공용 Traefik이 없습니다. make ops-deploy APP=ingress를 먼저 실행하세요.`, `공용 TLS 마운트가 없습니다` | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` 뒤 같은 명령 재실행 |
| `sso.etch.samsungds.net: 공용 TLS 인증서가 없습니다` | 인증서가 등록되지 않음. 파일이 있으면 [변경] `make ops-deploy APP=keycloak KUBE_CONTEXT="<context>"`의 준비 검사가 등록. 파일이 없으면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 준비 |
| `Keycloak 원본에 지정한 worker가 없거나 Ready가 아닙니다`, `Keycloak worker가 cordon 상태이거나 차단 taint가 있습니다` | [조회] `kubectl --context "<context>" get node khplane01w09`로 상태를 확인하고 [장애 조회](../README.md#장애-조회)의 Node NotReady 행을 따름 |
| `keycloak-runtime: 기존 Secret과 입력이 다릅니다` | [기존 Secret과 env가 다른 경우](docs/03-operations.md#기존-secret과-env가-다른-경우)의 조회와 조치. 조치 뒤에도 같으면 아래 멈춤 조건 |
| `설정 중단: 필수 설정 누락: CORP_OIDC_…`, `설정 중단: 실제 값으로 교체할 설정: …` | AD FS client 값이 env에 없음. [AD FS](../shared/docs/infrastructure/access.md#ad-fs) 절로 준비하고 `make keycloak-oidc-check KUBE_CONTEXT="<context>"`로 확인 |
| `설정 중단: 입력 파일 또는 discovery 접속/JSON 처리가 실패했습니다.`, `설정 중단: 발급받은 client 인증 방식이 discovery 지원 목록과 다릅니다.` | 관리 호스트의 Discovery URL 접근·CA 신뢰, client 인증 방식. [Discovery 해석 규칙](docs/02-configure.md#discovery-해석-규칙) |
| `keycloak-idp-mappers-setup` 로그의 `realm의 Email as username 설정` 조회 또는 변경 확인 실패 | Keycloak 관리자 권한과 Job 로그를 확인한 뒤 [User Profile과 수신 mapper](docs/02-configure.md#user-profile과-수신-mapper)의 명령을 다시 실행 |
| `초기 설정 실패:` 뒤가 CSV 형식 오류(`CSV 헤더 오류`, `열 수가 맞지 않습니다`, `올바르지 않습니다`, `중복입니다`) | CSV 오류. 헤더·열 수·공백 같은 형식은 [입력 파일 검사](docs/02-configure.md#1-입력-파일-검사)의 규칙으로 고쳐 선택 절의 1단계부터 다시 실행. 받은 데이터의 값이 틀렸으면(중복 EPID, 목록에 없는 SDWT) 오류의 행 번호를 보고 |

다음이면 멈추고 보고합니다.

- `기존 PVC가 있으나 keycloak-runtime이 없습니다`, `기존 PV가 있으나 keycloak-runtime이 없습니다`, `기존 PV가 Released 상태이거나 이전 PVC를 참조합니다`. 보존된 DB가 있습니다. PV·PVC·namespace·`claimRef`·Worker 폴더를 지우거나 고치지 않고, Secret을 새 값으로 만들지 않습니다. [설명](docs/03-operations.md#기존-dbnamespace를-복구하는-경우)
- `keycloak-runtime: 기존 Secret과 입력이 다릅니다`가 위 표의 조치 뒤에도 남음. Secret을 지우거나 다시 만들지 않고 `make k8s-env APP=keycloak`을 실행하지 않습니다.
- SDWT 적용이 `초기 설정 실패:`의 `기존 계정 신원이 충돌합니다`, `기존 계정의 … 다릅니다`, `CSV와 다른 위치`, `realm 기본 그룹이 있습니다`로 끝남. 기존 사용자·그룹·기본 그룹을 지우거나 옮기지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비](docs/01-prepare.md) | 설치 범위, Worker 디스크 확인, env 키와 검사, TLS·CA 준비 |
| [로그인·그룹·앱 연결](docs/02-configure.md) | 설정 단계와 Job, Discovery 해석, 설정 완료 확인, SDWT 그룹·사용자 CSV, 소속별 역할, 앱 연결, 앱 역할 카탈로그, 사용자 필드와 claim |
| [운영 작업](docs/03-operations.md) | 원본 위치와 도구, Secret 불일치와 기존 DB 복구, 공개 인증 주소 변경 |
| [앱 역할 카탈로그](access/README.md) | `access/catalog.json`의 역할 |
| [SDWT 등록 입력 템플릿](inputs/README.md) | SDWT·사용자 CSV 양식 |
