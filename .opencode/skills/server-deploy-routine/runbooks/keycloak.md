# Keycloak 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/keycloak/README.md) · [준비](../../../../deploy/keycloak/docs/01-prepare.md) · [배포](../../../../deploy/keycloak/docs/02-deploy.md) · [설정](../../../../deploy/keycloak/docs/03-configure.md) · [운영](../../../../deploy/keycloak/docs/04-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `etch-sso` (공용 Traefik과 같은 namespace) |
| 실행 Worker | `khplane01w09`, DB 데이터 `/appdata/keycloak-postgres` |
| 공개 주소 | `https://sso.etch.samsungds.net`, realm `etch`, 사내 IdP alias `oidc` |
| 배포 명령 | `make keycloak-check` → `make keycloak-up` (성공 시 배포 기록 자동) |
| 완료 기준 | PV·PVC `Bound`, postgres·keycloak·traefik rollout 성공, discovery issuer가 `https://sso.etch.samsungds.net/realms/etch`, 사람이 Account Console 사내 로그인 확인 |
| 먼저 필요한 것 | 공용 TLS(`sso.etch.samsungds.net`), Worker 폴더, 사내 AD FS client |

## 사람이 해야 하는 일

agent는 아래 일을 직접 하지 않습니다. 필요하면 사용자에게 요청하고 완료를 확인받은 뒤 진행합니다.

- [사람] Worker `khplane01w09`에서 `sudo install -d -m 0700 /appdata/keycloak-postgres`, 디스크 여유와 80/443 사용 확인
- [사람] 인증서 발급과 `deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt`·`private.key` 배치
- [사람] DNS `sso.etch.samsungds.net` → APP VIP 등록
- [사람] 사내 AD FS client 발급과 redirect URI `https://sso.etch.samsungds.net/realms/etch/broker/oidc/endpoint` 등록
- [사람] env 파일 작성(비밀번호 입력)
- [사람] Admin Console에서 `Email as username`이 꺼져 있는지 확인, Account Console 시험 로그인
- [사람] 관리 API 단계(SDWT·소속 역할·앱 역할)의 관리자 비밀번호 입력

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `KEYCLOAK_ENV` | Keycloak env 경로 | `deploy/keycloak/env/prod.env`. 외부 경로를 쓰면 모든 단계에 같은 값을 붙임 |
| `VIP_BACKENDS` | 공용 Traefik backend 노드 | 비움(현재 배치 보존). 검사가 VIP 불일치로 멈출 때만 사람에게 값을 받음 |
| env 필수 키 | `postgres-password`, `bootstrap-admin-username`, `bootstrap-admin-password`, `keycloak-public-url`, `CORP_OIDC_DISCOVERY_URL`, `CORP_OIDC_CLIENT_ID`, `CORP_OIDC_CLIENT_SECRET`, `CORP_OIDC_CLIENT_AUTH_METHOD`, `CORP_OIDC_VALIDATE_SIGNATURE` | 값은 읽거나 출력하지 않음 |

## A. 최초 설치

각 단계가 성공해야 다음 단계로 갑니다. 실패하면 [멈추고 사람에게 묻는 조건](#멈추고-사람에게-묻는-조건)과 원본 문서를 확인하고 보고합니다.

1. [조회] 사람 작업 완료 확인: 위 [사람이 해야 하는 일](#사람이-해야-하는-일)의 Worker 폴더·인증서 배치·AD FS·env 작성이 끝났는지 사용자에게 확인합니다.
2. [검사] env 형식 검사
   ```bash
   make env-check APP=keycloak PROFILE=prod COMPONENT=server
   make server-check APP=keycloak PROFILE=prod
   ```
   성공: `설정 검사 통과`, `서버 원본 검사 통과: keycloak/prod`. 이 검사는 기본 경로 env만 봅니다.
3. [변경] 공용 TLS 등록(승인 필요)
   ```bash
   make ingress-tls-up KUBE_CONTEXT=kubernetes-admin@kubernetes TLS_HOST=sso.etch.samsungds.net TLS_CERT_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/fullchain.crt" TLS_KEY_FILE="$PWD/deploy/shared/certs/sso.etch.samsungds.net/private.key"
   ```
   실패: SAN·체인·만료 오류면 멈추고 보고합니다([인증서 준비](../../../../deploy/shared/docs/certificates/prepare.md)).
4. [검사] 배포 전 검사(클러스터 변경 없음)
   ```bash
   make keycloak-check KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `Keycloak 입력·원본·기존 Secret·worker 검사 통과`. 실패하면 5단계로 가지 않습니다.
5. [변경] 배포(승인 필요)
   ```bash
   make keycloak-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `Keycloak 배포 완료: https://sso.etch.samsungds.net`과 `배포 기록 저장: etch-sso/deploy-record-keycloak`.
6. [조회] 기동 확인: [C. 배포 후 확인](#c-배포-후-확인)의 명령을 실행합니다.
7. [변경] realm 생성(승인 필요). Job이 최대 15분 걸립니다.
   ```bash
   make keycloak-realm-setup KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
8. [검사] IdP 사전 검사
   ```bash
   python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context kubernetes-admin@kubernetes --env deploy/keycloak/env/prod.env
   ```
   성공: `사전 검사 통과`. 실패하면 AD FS·Discovery URL·CA 문제이므로 멈추고 보고합니다.
9. [변경] 사내 IdP 등록(승인 필요)
   ```bash
   make keycloak-idp-setup KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
10. [변경] 사용자 프로필 등록(승인 필요)
    ```bash
    make keycloak-profile-setup KUBE_CONTEXT=kubernetes-admin@kubernetes
    ```
11. [사람] Admin Console에서 `Email as username`이 꺼져 있는지 사용자에게 확인받습니다.
12. [변경] IdP mapper 등록(승인 필요)
    ```bash
    make keycloak-idp-mappers-setup KUBE_CONTEXT=kubernetes-admin@kubernetes
    ```
13. [사람] Account Console(`https://sso.etch.samsungds.net/realms/etch/account/`) 사내 로그인과 Admin Console의 사용자 claim 값 확인을 요청합니다. 확인 전에는 다른 앱을 연결하지 않습니다.

7~12단계 중 하나가 실패하면 Job 로그를 확인합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get jobs
kubectl --context kubernetes-admin@kubernetes -n etch-sso logs job/<실패한 Job 이름>
kubectl --context kubernetes-admin@kubernetes -n etch-sso describe job <실패한 Job 이름>
```

Job 이름: `keycloak-realm-setup`, `keycloak-oidc-setup`, `keycloak-user-profile-setup`, `keycloak-idp-mappers-setup`.

### 선택: SDWT 소속·역할 (관리 API)

SDWT 권한을 쓸 때만 실행합니다. 관리자 비밀번호는 사람이 입력해야 하므로 사용자에게 실행을 요청하거나 함께 진행합니다. CSV는 저장소 밖에 둡니다. 절차는 [SDWT 그룹·사용자](../../../../deploy/keycloak/docs/03-configure.md#sdwt-그룹사용자)를 따릅니다.

| 순서 | 구분 | 명령 |
| --- | --- | --- |
| 1 | [검사] CSV만 검사 | `make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=1` |
| 2 | [조회] dry-run | `make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0` |
| 3 | [변경] 적용 | `make keycloak-sdwt-init KEYCLOAK_SDWT_CLIENTS= KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0` |
| 4 | [조회]→[변경] 소속별 역할 | `make keycloak-org-sync` → `make keycloak-org-sync KEYCLOAK_ORG_APPLY=1` |
| 5 | [조회]→[변경] 앱 역할 | `make keycloak-access-apply` → `make keycloak-access-apply KEYCLOAK_ACCESS_APPLY=1` |

dry-run 결과를 사용자에게 보여 주고 승인을 받은 뒤 적용합니다. 다시 실행해 `계획: 변경 없음`이 나오면 정상입니다.

## B. 업데이트

변경된 파일에 맞는 행만 실행합니다. 변경 파일은 `make drift-check APP=keycloak KUBE_CONTEXT=kubernetes-admin@kubernetes`의 `record` 항목으로 확인합니다.

| 변경 | 실행 |
| --- | --- |
| 문서만 | 없음 |
| `deploy/keycloak/k8s/` manifest·이미지 태그 | A-4 `keycloak-check` → A-5 `keycloak-up` → C |
| IdP·프로필·mapper 설정 | A-9·A-10·A-12 중 해당 단계만 다시 실행(기존 Job을 지우고 새로 만듦) |
| 인증서 갱신 | A-3 `ingress-tls-up` |
| `deploy/keycloak/access/catalog.json` | 선택 절의 4·5단계(dry-run 후 승인) |
| env의 DB·관리자 비밀번호 | 멈추고 사람에게 묻기. env만 바꿔서는 실제 서비스 값이 바뀌지 않고 `keycloak-up`이 중단함 |
| 공개 주소 변경 | 멈추고 사람에게 묻기. [공개 인증 주소 변경](../../../../deploy/keycloak/docs/04-operations.md#공개-인증-주소-변경) 절차 |

외부 env를 쓰는 환경에서는 검사·배포·IdP 단계에 같은 경로를 붙입니다.

```bash
make keycloak-check KUBE_CONTEXT=kubernetes-admin@kubernetes KEYCLOAK_ENV=<env 절대 경로>
make keycloak-up KUBE_CONTEXT=kubernetes-admin@kubernetes KEYCLOAK_ENV=<env 절대 경로>
```

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context kubernetes-admin@kubernetes get pv keycloak-postgres-data
kubectl --context kubernetes-admin@kubernetes -n etch-sso get pvc keycloak-postgres-data
kubectl --context kubernetes-admin@kubernetes -n etch-sso rollout status statefulset/keycloak-postgres --timeout=5m
kubectl --context kubernetes-admin@kubernetes -n etch-sso rollout status deployment/keycloak --timeout=10m
kubectl --context kubernetes-admin@kubernetes -n etch-sso rollout status deployment/traefik --timeout=5m
kubectl --context kubernetes-admin@kubernetes -n etch-sso get pods -o wide
curl -fsS https://sso.etch.samsungds.net/realms/etch/.well-known/openid-configuration
make drift-check APP=keycloak KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: PV·PVC `Bound`, keycloak·postgres Pod가 `khplane01w09`에서 Running, curl 결과의 `issuer`가 `https://sso.etch.samsungds.net/realms/etch`, drift-check 종료 코드 `0`.
curl은 DNS 전환 전에는 실패할 수 있습니다. 이때는 DNS 상태를 [인프라 정보](../../../../deploy/shared/docs/infrastructure/pending.md)에서 확인하고 보고합니다.

실패하면 조회합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n etch-sso get events --sort-by=.lastTimestamp
kubectl --context kubernetes-admin@kubernetes -n etch-sso logs statefulset/keycloak-postgres --tail=100
kubectl --context kubernetes-admin@kubernetes -n etch-sso logs deployment/keycloak --tail=100
```

## 멈추고 사람에게 묻는 조건

- `keycloak-check`나 `keycloak-up`이 "기존 PVC(PV)가 있으나 keycloak-runtime이 없습니다", "PV가 Released" 등 DB·PV 문제로 멈춤. PV·PVC·namespace·claimRef·Worker 폴더를 건드리지 않습니다.
- 기존 Secret과 env가 다르다는 오류. Secret을 지우거나 다시 만들지 않습니다.
- VIP 배치 불일치로 검사가 멈춤. `VIP_BACKENDS` 값은 사람에게 받고 기존 backend를 빼지 않습니다.
- mapper 단계가 `Email as username` 때문에 멈춤
- SDWT 적용이 중복 신원·기존 그룹 속성·위치 불일치로 멈춤
- org-sync·access-apply가 고아 역할 경고를 출력함(삭제는 사람이 Admin Console에서)
- `make k8s-env APP=keycloak ...`이나 `deploy/keycloak/rendered/` 적용이 필요해 보이는 경우. 이 명령들은 기존 Secret·라우팅을 덮어쓰므로 실행하지 않습니다.
