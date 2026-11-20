# Keycloak 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

사내 인증 서버(Keycloak)를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 사내 AD FS 로그인을 중계하는 인증 서버. Portal·Headlamp·Airflow가 각자 전용 client로 realm `etch`에 연결 |
| namespace | `etch-sso` (공용 Traefik과 같은 namespace) |
| 실행 Worker | `khplane01w09`, DB 데이터 `/appdata/keycloak-postgres`(없으면 `keycloak-up`이 생성) |
| 공개 주소 | `https://sso.etch.samsungds.net`, realm `etch`, 사내 IdP alias `oidc` |
| 배포 명령 | `make ops-deploy APP=keycloak` = `keycloak-check` → `keycloak-up` → `keycloak-setup` → `keycloak-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, discovery issuer가 `https://sso.etch.samsungds.net/realms/etch` |
| 먼저 필요한 것 | 공용 TLS(`sso.etch.samsungds.net`), 사내 AD FS client 값이 env에 있음 |

## 구성

- 서버: Keycloak 26.7.1과 전용 PostgreSQL 16을 각각 단일 replica로 실행합니다.
- 저장: 지정 Worker 한 대의 정적 local PV 50Gi(`Retain`)입니다. 단일 Worker의 로컬 디스크에 의존하므로 HA가 아니며 PostgreSQL 외부 백업을 별도로 준비합니다.
- 접속: DNS → APP VIP → 공용 Traefik(Worker host port 80/443에서 TLS 종료) → Keycloak입니다. 인증서는 공용 `etch-sso/traefik-tls`에 등록하고, 공용 Traefik(`deploy/shared/ingress`)은 Keycloak 배포가 함께 적용합니다.
- 로그인: 사내 AD FS에서 발급받은 client로 사내 IdP(`oidc`)에 연결합니다. 사내 claim은 IdP mapper가 사용자 필드로 받고 앱별 mapper가 토큰으로 발급합니다([사용자 필드와 claim](docs/02-configure.md#사용자-필드와-claim)).
- 설정: `keycloak-setup`이 realm → 사내 IdP → 사용자 프로필 → IdP mapper를 Job으로 등록합니다. SDWT 소속·역할과 앱 역할은 관리 API 도구로 따로 반영합니다.
- 앱 연결: 앱 client는 각 앱의 배포가 등록합니다([앱 연결](docs/02-configure.md#앱-연결)). 최초 설치에는 Portal client secret이 필요하지 않습니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 인증서 발급과 `deploy/shared/certs/sso.etch.samsungds.net/` 배치([방법](docs/01-prepare.md#tlsca-준비)) | `ls -l deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt deploy/shared/certs/sso.etch.samsungds.net/private.key` |
| DNS `sso.etch.samsungds.net` → APP VIP 등록 | `getent hosts sso.etch.samsungds.net` |
| 사내 AD FS client 발급, redirect URI `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint` 등록, 발급값을 Keycloak env의 `CORP_OIDC_CLIENT_ID`·`CORP_OIDC_CLIENT_SECRET`에 반영([입력 키](docs/01-prepare.md#사내-identity-provider용-값)) | `make ops-preflight APP=keycloak PROFILE=prod KUBE_CONTEXT="<context>"`가 env를 통과 |
| 선택: Account Console 사내 로그인 시험([방법](docs/02-configure.md#설정-완료-확인)) | 사용자 보고 |

DNS가 아직 없어도 배포는 진행합니다. smoke만 `SMOKE_CONNECT`로 확인합니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `KEYCLOAK_ENV` | Keycloak env 경로 | `deploy/keycloak/env/prod.env`. 외부 경로를 쓰면 모든 명령에 같은 값을 붙임 |
| `VIP_BACKENDS` | 공용 Traefik backend 노드 | 비움(현재 배치 보존) |
| 관리자 계정 | 관리 API 도구(SDWT·소속·앱 역할)의 로그인 | Make가 env의 `bootstrap-admin-username`·`bootstrap-admin-password`를 자동 전달 |

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

1. [검사] 인증서 파일 확인: 위 표의 `ls` 명령. 없으면 인증서 배치를 요청하고 멈춥니다.
2. [변경] 공용 Traefik 준비: [공통 Traefik 검사·갱신](../README.md#공용-traefik-검사갱신)의 `ingress-check`가 실패하면 `ingress-up`을 실행합니다.
3. [변경] 공용 TLS 등록
   ```bash
   make ingress-tls-up KUBE_CONTEXT="<context>" TLS_HOST=sso.etch.samsungds.net TLS_CERT_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/private.key"
   ```
4. [변경] 배포와 설정. DB 폴더 준비, 스택 적용, realm·사내 IdP·사용자 프로필·IdP mapper 등록(각 Job 최대 15분), smoke, 대조를 순서대로 수행합니다.
   ```bash
   make ops-deploy APP=keycloak KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
   `keycloak-smoke`만 `DNS 조회 실패`로 실패하면 배포는 끝난 것입니다. [조회] 아래로 확인하고 DNS 등록을 요청합니다.
   ```bash
   make keycloak-smoke KUBE_CONTEXT="<context>" SMOKE_CONNECT=<APP VIP 주소>
   ```
5. [조회] [C. 배포 후 확인](#c-배포-후-확인)

`keycloak-setup`이 실패하면 [문제 해결](#문제-해결과-멈춤-조건)의 Job 로그 조회를 따릅니다.

### 선택: SDWT 소속·역할 (관리 API)

SDWT 권한을 쓸 때만 실행합니다. CSV는 사용자가 저장소 밖 경로로 전달합니다. 관리자 계정은 Make가 env에서 자동으로 넘깁니다.

| 순서 | 구분 | 명령 |
| --- | --- | --- |
| 1 | [검사] CSV만 검사 | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1` |
| 2 | [조회] dry-run | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0` |
| 3 | [변경] 적용 | `make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="<SDWT CSV 절대 경로>" KEYCLOAK_USERS_CSV="<사용자 CSV 절대 경로>" KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0` |
| 4 | [조회]→[변경] 소속별 역할 | `make keycloak-org-sync` → `make keycloak-org-sync KEYCLOAK_ORG_APPLY=1` |
| 5 | [조회]→[변경] 앱 역할 | `make keycloak-access-apply` → `make keycloak-access-apply KEYCLOAK_ACCESS_APPLY=1` |

dry-run 결과에 삭제·고아 역할 경고가 없으면 바로 적용합니다. 다시 실행해 `계획: 변경 없음`이 나오면 정상입니다.
CSV 경로는 사용자가 전달한 실제 경로로 바꿉니다. 사용자 CSV가 없으면 `KEYCLOAK_USERS_CSV=...`를 빼고 실행하며 이때는 그룹 설정만 수행합니다. CSV 형식과 각 단계의 결과는 [SDWT 그룹·사용자](docs/02-configure.md#sdwt-그룹사용자), [소속별 역할](docs/02-configure.md#소속별-역할), [앱 역할](docs/02-configure.md#앱-역할)에 있습니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| 문서만 | 없음 |
| manifest·이미지 태그·IdP·프로필·mapper 설정 | [변경] `make ops-deploy APP=keycloak KUBE_CONTEXT="<context>"` |
| 인증서 갱신 | A-3 |
| `deploy/keycloak/access/catalog.json` | 선택 절의 4·5단계 |
| env의 DB·관리자 비밀번호 | 멈추고 사람에게 묻기. env만 바꿔서는 실제 서비스 값이 바뀌지 않고 `keycloak-up`이 중단함. [설명](docs/03-operations.md#secret-불일치와-기존-db-복구) |
| 공개 주소 변경 | 멈추고 사람에게 묻기. [방법](docs/03-operations.md#공개-인증-주소-변경) |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" get pv keycloak-postgres-data
kubectl --context "<context>" -n etch-sso get pvc keycloak-postgres-data
kubectl --context "<context>" -n etch-sso get pods -o wide
make keycloak-smoke KUBE_CONTEXT="<context>"
```

성공: PV·PVC `Bound`, keycloak·postgres Pod Running, `smoke 통과: keycloak`.

## 문제 해결과 멈춤 조건

[조회] `keycloak-setup`이 실패하면 Job 로그를 확인합니다. Job 이름: `keycloak-realm-setup`, `keycloak-oidc-setup`, `keycloak-user-profile-setup`, `keycloak-idp-mappers-setup`.

```bash
kubectl --context "<context>" -n etch-sso get jobs
kubectl --context "<context>" -n etch-sso logs job/<실패한 Job 이름>
```

원인을 해결한 뒤 `make keycloak-setup KUBE_CONTEXT="<context>"`를 다시 실행합니다. 각 단계는 다시 실행해도 같은 결과입니다.

서버 기동이 실패하면 [조회]로 이벤트와 로그를 확인합니다. 그 밖의 증상은 [장애 조회](../README.md#장애-조회)를 따릅니다.

```bash
kubectl --context "<context>" -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context "<context>" -n etch-sso logs statefulset/keycloak-postgres
kubectl --context "<context>" -n etch-sso logs deployment/keycloak
kubectl --context "<context>" -n etch-sso logs deployment/traefik
```

| 증상 | 원인과 조치 |
| --- | --- |
| smoke `DNS 조회 실패` | DNS 등록 전. A-4의 `SMOKE_CONNECT` 명령으로 서비스 자체를 확인하고 DNS 등록을 요청. APP VIP 주소는 [별칭 표](../shared/docs/infrastructure/aliases.json)의 `VIP-APP` |
| `keycloak-runtime: 기존 Secret과 입력이 다릅니다` | env와 기존 Secret 불일치. Secret을 지우거나 다시 만들지 않고 멈춤. [설명](docs/03-operations.md#secret-불일치와-기존-db-복구) |
| `기존 PVC(PV)가 있으나 keycloak-runtime이 없습니다`, `기존 PV가 Released 상태이거나 이전 PVC를 참조합니다` | 보존된 DB의 복구가 필요. 멈춤. [설명](docs/03-operations.md#secret-불일치와-기존-db-복구) |
| IdP 사전 검사 실패 | Discovery URL 접근·CA 신뢰·client 인증 방식. [Discovery 해석 규칙](docs/02-configure.md#discovery-해석-규칙) |
| mapper Job이 `Email as username` 때문에 중단 | [사람] Admin Console의 `Realm settings`에서 끔. [방법](docs/02-configure.md#user-profile과-수신-mapper) |

멈추고 사람에게 묻는 조건입니다.

- `keycloak-check`나 `keycloak-up`이 "기존 PVC(PV)가 있으나 keycloak-runtime이 없습니다", "PV가 Released" 등 DB·PV 문제로 멈춤. PV·PVC·namespace·claimRef·Worker 폴더를 건드리지 않습니다.
- 기존 Secret과 env가 다르다는 오류. Secret을 지우거나 다시 만들지 않습니다.
- VIP 배치 불일치로 검사가 멈춤
- IdP 사전 검사 실패(AD FS·Discovery URL·CA 문제), mapper 단계가 `Email as username` 때문에 멈춤
- SDWT 적용이 중복 신원·기존 그룹 속성·위치 불일치로 멈춤, org-sync·access-apply가 고아 역할 경고를 출력함

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설치 준비](docs/01-prepare.md) | 설치 범위, Worker 디스크·포트 확인, env 키와 검사, TLS·CA 준비 |
| [로그인·그룹·앱 연결](docs/02-configure.md) | 설정 단계와 Job, Discovery 해석, 설정 완료 확인, SDWT 그룹·사용자 CSV, 소속별 역할, 앱 연결, 앱 역할 카탈로그, 사용자 필드와 claim |
| [운영 작업](docs/03-operations.md) | 원본 위치와 도구, Secret 불일치와 기존 DB 복구, 공개 인증 주소 변경 |
| [앱 역할 카탈로그](access/README.md) | `access/catalog.json`의 역할 |
| [SDWT 등록 입력 템플릿](inputs/README.md) | SDWT·사용자 CSV 양식 |
