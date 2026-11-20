# Keycloak 운영 작업

[Keycloak 가이드](../README.md) · [관리 호스트 공통 Git·파일 관리](../../shared/docs/operations/01-checkout.md#git운영-파일-관리)

설치·업데이트 절차는 [Keycloak 가이드](../README.md)에 있습니다. 이 문서는 원본과 도구의 구조, 그 밖의 운영 작업입니다.
관리 호스트는 배포 명령을 실행하는 호스트이며 Keycloak·PostgreSQL은 manifest에 지정한 Worker에서 실행됩니다. 저장소 갱신과 Kubernetes·사용자 설정 적용은 별개의 작업입니다.

- [원본 위치와 도구](#원본-위치와-도구)
- [Secret 불일치와 기존 DB 복구](#secret-불일치와-기존-db-복구)
- [공개 인증 주소 변경](#공개-인증-주소-변경)

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
| `k8s/claims/sdwt-access-scope.json` | 라인·SDWT groups 공통 scope |
| `inputs/` | SDWT·사용자 등록 CSV 양식 |
| `access/catalog.json` | 앱 역할 카탈로그. [앱 역할](02-configure.md#앱-역할) |
| `deploy/shared/certs/sso.etch.samsungds.net/` | 사이트 인증서. Git에 포함하지 않음 |
| Worker `/appdata/keycloak-postgres` | PostgreSQL 실제 데이터. Git checkout에 포함되지 않음 |

| 도구 | 호출 경로·역할 |
| --- | --- |
| `scripts/up.py` | `keycloak-check`·`keycloak-up`의 서버 검사·배포 |
| `scripts/setup_discovery.py` | 설정 Job 실행과 Discovery 해석. `keycloak-oidc-check`·`keycloak-oidc-setup`은 IdP·mapper·선택 Portal client를 한 번에 실행 |
| `scripts/00`~`05` 실행 파일 | Make 단계별 명령의 진입점. `keycloak-setup`은 `00`~`03`을 순서대로 실행 |
| `scripts/admin_env.py` | 관리 API 도구에 env의 관리자 계정을 환경변수로 전달. `KEYCLOAK_ADMIN_URL`·`USERNAME`·`PASSWORD` 중 하나라도 직접 지정하면 전달하지 않음 |
| `scripts/init_sdwt.py` | `/org` 소속 그룹·사용자 등록과 공통 scope 연결. 적용 시 `org_sync.py`도 실행 |
| `scripts/org_sync.py` | `keycloak-org-sync`의 소속별 역할·라인/팀 묶음·`org-claims` scope 반영. [소속별 역할](02-configure.md#소속별-역할) |
| `scripts/access_apply.py` | `keycloak-access-apply`의 앱 역할·기본 역할·권한관리 웹 카탈로그 반영 |

설정 Job은 선택한 context에 관리 ConfigMap `keycloak-claim-mapper`를 적용한 뒤 실행합니다.
프로필 단계는 `KEYCLOAK_PROFILE_ONLY=true`, 수신 mapper 단계는 `KEYCLOAK_SKIP_PROFILE=true`로 같은 Job 원본을 구분합니다.
Portal client Job은 `deploy/portal/k8s/jobs/keycloak-client`가 소유합니다.

### 배포 명령의 처리 범위

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-check` | env·인증서·manifest·기존 Secret·PV/PVC·worker 상태를 조회하고 검사. 클러스터 변경 없음 |
| `keycloak-up` | 없는 runtime Secret 생성, 공용 TLS 확인, 새 PV일 때 DB 폴더 준비 Job, PostgreSQL·Keycloak·Traefik 적용 후 rollout 대기 |
| `keycloak-setup` | Realm → 사내 IdP 사전 검사 → 사내 IdP → User Profile → IdP mapper Job. [설정 단계와 Job](02-configure.md#설정-단계와-job) |
| `keycloak-smoke` | 워크로드 Ready와 공개 주소의 discovery 응답을 조회 |

최초 기동 시 관리자 계정을 만들고 이후 설정 Job도 같은 runtime Secret으로 로그인합니다.
`etch-sso` namespace가 없을 때만 원본의 label·annotation으로 생성하며, 이미 있으면 namespace 설정은 변경하지 않습니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `KEYCLOAK_ENV=/절대/경로/prod.env` | 다른 env 파일 사용. 모든 명령에 동일하게 전달 |
| `KEYCLOAK_CERTS=/인증서/폴더` | 해당 폴더의 `fullchain.crt`·`private.key`를 배포와 함께 공용 TLS에 등록 |
| `VIP_BACKENDS=...` | VIP 최초 배치 지정. 검사·배포 양쪽에 동일하게 전달 |

VIP backend 값은 [네트워크 정보](../../shared/docs/infrastructure/network.md)에서 확인합니다.
공용 Ingress가 이미 운영 중이면 기존 감시 namespace·replica·Worker pool·affinity·VIP annotation을 유지합니다.
기록된 VIP와 배치가 다르면 검사에서 중단하며, 확인한 `VIP_BACKENDS`를 검사·배포 양쪽에 명시하면 기존 Backend를 포함해 배치를 다시 계산합니다. Keycloak·DB의 전용 Worker 조건은 별도로 유지합니다.
[승인] `VIP_BACKENDS` 지정은 서비스 진입 경로를 바꾸므로 [공용 Traefik 검사·갱신](../../README.md#공용-traefik-검사갱신)의 규칙을 따릅니다.

## Secret 불일치와 기존 DB 복구

이 절의 복구는 실제 credential과 보존할 DB를 아는 운영자가 판단합니다. 도구는 PV의 `claimRef`를 지우거나 데이터·namespace·PVC·Secret을 삭제하지 않습니다.

### 기존 Secret과 env가 다른 경우

`keycloak-up`은 `keycloak-runtime` Secret이 없을 때만 만듭니다. 기존 Secret과 env가 다르면 검사·배포 모두 `keycloak-runtime: 기존 Secret과 입력이 다릅니다`로 중단합니다.
DB·관리자 비밀번호는 env와 Secret만 바꾼다고 실제 서비스의 값이 바뀌지 않습니다. 불일치가 발견되면 실제 값과 원본을 먼저 확인하고 env를 기존 값에 맞춥니다.
Secret을 삭제하거나 DB·관리자 비밀번호를 재생성하지 않습니다. `make k8s-env APP=keycloak ...`은 기존 Secret을 덮어쓰므로 실행하지 않습니다.
공개 URL만 바꾸는 경우는 [공개 인증 주소 변경](#공개-인증-주소-변경)을 따릅니다.

### 기존 DB·namespace를 복구하는 경우

`keycloak-runtime`이 없고 DB의 PVC 또는 PV가 남아 있으면 검사·배포 모두 적용 전에 중단합니다.
PV가 `Available`이어도 디스크가 비어 있다고 단정할 수 없으므로 같은 규칙을 적용합니다.
기존 DB의 실제 비밀번호·관리자 설정을 확인하고 runtime Secret을 먼저 복원한 뒤 다시 검사합니다.

namespace 삭제로 PVC·Secret이 사라져도 `Retain` PV와 Worker의 DB 파일은 남을 수 있습니다.
아래 조회로 바인딩 상태를 확인하고, DB 백업·실제 credential과 대조해 운영자가 복구합니다.

[조회]

```bash
kubectl --context "<context>" get pv keycloak-postgres-data \
  -o jsonpath='{.status.phase}{"\n"}{.spec.claimRef}{"\n"}'
kubectl --context "<context>" -n etch-sso get pvc keycloak-postgres-data \
  -o jsonpath='{.metadata.uid}{"\n"}'
```

PV가 `Released`이거나 이전 PVC의 UID를 참조하면 runtime Secret을 복원했어도 배포를 중단합니다.
운영자가 보존할 DB와 바인딩 복구를 확인한 뒤 `make keycloak-check KUBE_CONTEXT="<context>"`부터 다시 실행합니다.

## 공개 인증 주소 변경

[승인] Keycloak 공개 주소와 issuer를 바꿉니다. 로그인 서비스가 재시작되고 모든 앱의 issuer가 함께 바뀌어야 하므로 사용자 요청과 승인이 있을 때만 수행합니다.
운영 공개 주소는 `https://sso.etch.samsungds.net`, realm issuer는 `https://sso.etch.samsungds.net/realms/etch`입니다.
테스트 SSO 주소 계획은 [네트워크 정보](../../shared/docs/infrastructure/network.md)를 따르며 이 절차로 별도 테스트 SSO를 만들지 않습니다.

준비물은 새 이름의 DNS·VIP 경로(DNS 변경은 사용자가 직접 수행), SAN·CA 체인·만료를 확인한 인증서, 기존 credential과 일치하고 `keycloak-public-url`만 새 주소인 env입니다.
앱 callback 경로·client ID·secret·계정·권한·realm·DB·namespace와 내부 Service 주소는 유지합니다.
명령은 관리 호스트의 저장소 루트에서 실행합니다. 외부 env 파일을 쓰면 아래 명령의 env 경로를 그 파일로 바꾸고 Make 명령에 `KEYCLOAK_ENV="<env 절대 경로>"`를 붙입니다.

### 1. 인증서와 AD FS 준비

새 도메인 인증서를 준비해 [공용 TLS 등록](../../README.md#공용-tls-등록)으로 먼저 등록하고, AD FS에 새 broker redirect URI(`<새 공개 URL>/realms/etch/broker/oidc/endpoint`)를 등록합니다.

### 2. 기존 Secret의 공개 URL 갱신

최초 설치라면 이 단계를 건너뛰고 새 env로 [가이드의 최초 설치](../README.md#a-최초-설치)를 진행합니다.
기존 `keycloak-runtime`이 있으면 배포 도구는 env와 불일치할 때 중단합니다. 이때 Secret을 삭제하거나 DB·관리자 비밀번호를 재생성하지 않습니다.

[승인] 아래 명령은 **기존 Secret이 있을 때만** 실행합니다. Secret의 `keycloak-public-url`만 갱신하며 비밀번호·다른 키는 변경하거나 출력하지 않습니다.

```bash
set -o pipefail
python3 - deploy/keycloak/env/prod.env <<'PY' | kubectl --context "<context>" -n etch-sso patch secret keycloak-runtime --type=merge --patch-file=/dev/stdin
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

성공: `secret/keycloak-runtime patched`. URL 형식이 틀리면 Secret을 변경하지 않고 중단합니다.

### 3. 검사·배포와 재시작

같은 context·env로 실행합니다. Pod는 Secret의 env 변경만으로 재시작되지 않으므로 배포 후 재시작합니다.

[검사]

```bash
make keycloak-check KUBE_CONTEXT="<context>"
```

[승인] 배포하고 Keycloak을 재시작합니다.

```bash
make keycloak-up KUBE_CONTEXT="<context>"
kubectl --context "<context>" -n etch-sso rollout restart deployment/keycloak
kubectl --context "<context>" -n etch-sso rollout status deployment/keycloak --timeout=10m
```

### 4. 앱 issuer 반영

Portal·Airflow·Headlamp의 운영 env와 실제 배포 입력의 issuer를 새 주소로 맞추고 해당 앱의 절차로 반영합니다.
realm에 별도의 Frontend URL을 지정했다면 새 공개 주소와 일치하는지 확인합니다.
API server OIDC가 구성되어 있다면 [모든 API server의 issuer와 CA](../../shared/docs/kubernetes/oidc.md)를 맞춥니다.

### 5. 확인

[조회] [가이드의 배포 후 확인](../README.md#c-배포-후-확인)을 실행하고, discovery 응답에서 issuer와 endpoint가 새 공개 주소인지 확인합니다.

```bash
curl -fsS <새 공개 URL>/realms/etch/.well-known/openid-configuration
```

[사람] 새 토큰의 issuer, AD FS 사내 로그인, 각 앱의 로그인·로그아웃, Headlamp 자원 조회까지 성공해야 완료입니다.
