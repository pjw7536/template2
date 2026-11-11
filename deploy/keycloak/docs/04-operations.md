# Keycloak 운영과 원본 관리

[앱 안내](../README.md) · [CP1 공통 Git·파일 관리](../../shared/docs/operations/01-checkout.md#git운영-파일-관리)

CP1은 배포 명령을 실행하는 호스트이며 Keycloak·PostgreSQL은 manifest에 지정한 Worker에서 실행됩니다.
저장소 갱신과 Kubernetes·사용자 설정 적용은 별개의 작업입니다. 최초 설치는 [README](../README.md)의 순서를 따릅니다.

- [원본 위치와 도구](#원본-위치와-도구)
- [저장소 갱신 후 반영](#저장소-갱신-후-반영)
- [외부 env 파일을 사용하는 환경](#외부-env-파일을-사용하는-환경)
- [공개 인증 주소 변경](#공개-인증-주소-변경)
- [전달용 YAML](#전달용-yaml)
- [사내 claim 속성 이전](#사내-claim-속성-이전)

## 원본 위치와 도구

| 원본 | 역할 |
| --- | --- |
| `env/prod.env` | 서버·사내 IdP 설정값 |
| `k8s/kustomization.yaml` | 서버·공용 ingress(`deploy/shared/ingress`)·이미지·관리 ConfigMap 구성 |
| `k8s/server/stack.yaml` | PostgreSQL·Keycloak·PV/PVC·Service·Ingress |
| `k8s/server/etch-realm.json` | 최초 `etch` realm 정의 |
| `k8s/oidc/setup-realm.sh`, `setup-oidc.sh` | realm 준비, 사내 IdP 연결 등록 |
| `k8s/oidc/oidc-setup-job.yaml` | IdP Job 원본. Realm Job에도 재사용 |
| `k8s/claims/account-user-profile.json` | 사용자 필드·조회/편집 권한 |
| `k8s/claims/sync-oidc-claim-mappers.sh` | 수신·발급 mapper 등록 |
| `k8s/claims/claim-mappers-job.yaml` | 프로필·mapper Job 원본 |
| `k8s/claims/sdwt-access-scope.json` | SDWT groups 공통 scope |
| `inputs/` | SDWT·사용자 등록 CSV 양식 |
| `deploy/shared/certs/sso.etch.samsungds.net/` | 사이트 인증서. Git에 포함하지 않음 |
| Worker `/appdata/keycloak-postgres` | PostgreSQL 실제 데이터. Git checkout에 포함되지 않음 |

| 도구 | 호출 경로·역할 |
| --- | --- |
| `scripts/up.py` | `keycloak-check`·`keycloak-up`의 서버 검사·배포 |
| `scripts/setup_discovery.py` | 설정 Job 실행과 Discovery 해석. `keycloak-oidc-check`·`keycloak-oidc-setup`은 IdP·mapper·선택 Portal client를 한 번에 실행 |
| `scripts/00`~`05` 실행 파일 | Make 단계별 명령의 진입점 |
| `scripts/init_sdwt.py` | SDWT 그룹·사용자 등록과 공통 scope 연결 |
| `scripts/render.sh` | `make k8s-export`의 전달 YAML 생성 |
| `scripts/migrate_claim_attributes.py` | [사내 claim 속성 이전](#사내-claim-속성-이전) |

설정 Job은 선택한 context에 관리 ConfigMap `keycloak-claim-mapper`를 적용한 뒤 실행합니다.
프로필 단계는 `KEYCLOAK_PROFILE_ONLY=true`, 수신 mapper 단계는 `KEYCLOAK_SKIP_PROFILE=true`로 같은 Job 원본을 구분합니다.
Portal client Job은 `deploy/portal/k8s/jobs/keycloak-client`가 소유합니다.

## 저장소 갱신 후 반영

[CP1 공통 안내](../../shared/docs/operations/01-checkout.md#git운영-파일-관리)에 따라 브랜치·변경사항을 확인하고 pull한 뒤 변경 종류에 맞는 절차를 사용합니다.

| 변경 내용 | 반영 절차 |
| --- | --- |
| 문서만 변경 | 서버 적용 불필요 |
| 서버 manifest | [검사 후 서버 배포](02-deploy.md#1-검사-후-서버-배포) |
| IdP·프로필·수신 mapper | [Realm과 사내 로그인](03-configure.md#realm과-사내-로그인)의 해당 단계 |
| 인증서 | [공용 TLS 등록](../../shared/docs/certificates/apply.md#2-공용-tls-secret-등록갱신--cp1) |
| Portal·Headlamp client | [앱 연결](03-configure.md#앱-연결) 및 해당 앱의 소유 문서 |

DB·관리자 비밀번호는 env와 Secret만 바꾼다고 실제 서비스의 값이 바뀌지 않습니다. 불일치가 발견되면 실제 값과 원본을 먼저 확인합니다.

## 외부 env 파일을 사용하는 환경

기본 입력은 `deploy/keycloak/env/prod.env`입니다. 외부 파일을 쓰는 서버에서는 검사·배포·IdP 단계에 **같은 파일 경로**를 `KEYCLOAK_ENV`로 전달하고 설정을 두 곳에 중복 관리하지 않습니다.

```bash
read -r -p '대상 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
read -r -p 'Keycloak env 절대 경로: ' KEYCLOAK_ENV_PATH
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
```

## 공개 인증 주소 변경

**목적:** Keycloak 공개 주소와 issuer를 바꿉니다. 운영 공개 주소는 `https://sso.etch.samsungds.net`, realm issuer는 `https://sso.etch.samsungds.net/realms/etch`입니다.
테스트 SSO 주소 계획은 [네트워크 정보](../../shared/docs/infrastructure/network.md)를 따르며 이 절차로 별도 테스트 SSO를 만들지 않습니다.

**준비물:** 새 이름의 DNS·VIP 경로(DNS 변경은 사용자가 직접 수행), SAN·CA 체인·만료를 확인한 인증서, 기존 credential과 일치하고 `keycloak-public-url`만 새 주소인 env.
앱 callback 경로·client ID·secret·계정·권한·realm·DB·namespace와 내부 Service 주소는 유지합니다.

**실행 위치:** CP1의 저장소 루트입니다.

### 1. 인증서와 AD FS 준비

새 도메인 인증서를 [공용 TLS 등록](../../shared/docs/certificates/apply.md)으로 먼저 등록하고, AD FS에 새 broker redirect URI(`<새 공개 URL>/realms/etch/broker/oidc/endpoint`)를 등록합니다.

### 2. 기존 Secret의 공개 URL 갱신

최초 설치라면 이 단계를 건너뛰고 새 env로 [검사 후 서버 배포](02-deploy.md#1-검사-후-서버-배포)를 진행합니다.
기존 `keycloak-runtime`이 있으면 배포 도구는 env와 불일치할 때 중단합니다. 이때 Secret을 삭제하거나 DB·관리자 비밀번호를 재생성하지 않습니다.

아래 명령은 **기존 Secret이 있을 때만** 실행합니다. Secret의 `keycloak-public-url`만 갱신하며 비밀번호·다른 키는 변경하거나 출력하지 않습니다.

```bash
read -r -p '대상 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
KEYCLOAK_ENV_PATH="${KEYCLOAK_ENV_PATH:-deploy/keycloak/env/prod.env}"
set -o pipefail
python3 - "$KEYCLOAK_ENV_PATH" <<'PY' | kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso patch secret keycloak-runtime --type=merge --patch-file=/dev/stdin
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

values = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#'):
        key, _, value = line.partition('=')
        values[key] = value
public_url = values['keycloak-public-url']
url = urlsplit(public_url)
if url.scheme != 'https' or not url.hostname or url.path or url.query or url.fragment or url.username or url.password:
    raise SystemExit('keycloak-public-url은 경로·credential 없는 HTTPS URL이어야 합니다.')
print(json.dumps({'stringData': {'keycloak-public-url': public_url}}))
PY
```

**기대 결과:** `secret/keycloak-runtime patched`. URL 형식이 틀리면 Secret을 변경하지 않고 중단합니다.

### 3. 검사·배포와 재시작

같은 context·env로 실행합니다. Pod는 Secret의 env 변경만으로 재시작되지 않으므로 배포 후 재시작합니다.

```bash
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
make keycloak-up KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout restart deployment/keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=10m
```

### 4. 앱 issuer 반영

Portal·Airflow·Headlamp의 운영 env와 실제 배포 입력의 issuer를 새 주소로 맞추고 해당 앱의 절차로 반영합니다.
realm에 별도의 Frontend URL을 지정했다면 새 공개 주소와 일치하는지 확인합니다.
API server OIDC가 구성되어 있다면 [모든 API server의 issuer와 CA](../../shared/docs/kubernetes/oidc.md)를 맞춥니다.

### 5. 확인

[서버 기동 확인](02-deploy.md#2-서버-기동-확인)의 discovery 응답에서 issuer와 endpoint가 새 공개 주소인지 확인합니다.
새 토큰의 issuer, AD FS 사내 로그인, 각 앱의 로그인·로그아웃, Headlamp 자원 조회까지 성공해야 완료입니다.

## 전달용 YAML

`rendered/`는 `make k8s-export`가 `export/`·`k8s/`·`deploy/shared/ingress` 원본에서 생성하는 전달 파일이며 직접 편집하지 않습니다. credential과 TLS 개인키는 포함하지 않습니다.

| 파일 | 내용 |
| --- | --- |
| `rendered/internal-keycloak-stack.yaml` | 서버 스택과 공용 ingress. Traefik replica 2, `ingress: traefik` 노드 라벨, `etch-sso,headlamp` 감시 범위 |
| `rendered/internal-keycloak-claim-mappers.yaml` | 관리 ConfigMap과 프로필·mapper Job |

일반 설치·재배포는 단계별 Make 명령을 사용하며 전달 YAML과 함께 적용하지 않습니다.
전달 스택은 Headlamp namespace 권한·ingress 노드 라벨이 준비된 환경용입니다. 공용 라우팅이 연결된 서버에 직접 적용하면 감시 범위·배치가 원본 값으로 바뀝니다.

## 사내 claim 속성 이전

**목적:** 기존 사용자의 커스텀 속성을 현재 사내 claim 이름으로 복사합니다. 최초 설치에는 사용하지 않습니다.

| 기존 속성 | 새 속성 |
| --- | --- |
| `knox_id` | `loginid` |
| `department` | `deptname` |
| `grd_name` | `grdName` |

**준비물:** [User Profile 등록](03-configure.md#3-user-profile-등록) 완료(새 속성 정의와 `ADMIN_EDIT` 정책 필요), 관리자 인증.

**실행 위치·입력:** 저장소 루트의 Bash에서 [관리자 인증 입력](03-configure.md#2-관리자-인증-입력)과 같은 환경변수(`KEYCLOAK_ADMIN_URL`, `KEYCLOAK_ADMIN_USERNAME`·`KEYCLOAK_ADMIN_PASSWORD` 또는 `KEYCLOAK_ADMIN_CLIENT_ID`·`KEYCLOAK_ADMIN_CLIENT_SECRET`, 필요 시 `KEYCLOAK_ADMIN_REALM`·`KEYCLOAK_CA_FILE`·`KEYCLOAK_TARGET_REALM`)를 설정합니다.

```bash
make keycloak-claim-attributes-migrate
make keycloak-claim-attributes-migrate KEYCLOAK_CLAIM_MIGRATION_APPLY=1
```

첫 명령은 dry-run으로 복사 대상 사용자 수만 출력하고, 두 번째 명령이 실제로 복사합니다.

**기대 결과:** 새 속성이 비어 있는 사용자만 기존 값으로 채워지고 기존 속성·사용자 ID·그룹·broker 연결은 유지됩니다.

**실패 확인:** 기존·새 속성값이 다르거나 단일 문자열이 아니면 쓰기 전에 중단합니다. 검사 후 사용자 속성이 바뀌면 그 사용자에서 중단하며 앞서 완료된 복사는 유지되므로 동시 수정을 멈추고 재실행합니다.
