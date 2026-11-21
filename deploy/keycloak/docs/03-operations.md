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
| `k8s/kustomization.yaml` | 서버·이미지·관리 ConfigMap 구성. 공용 Traefik은 포함하지 않으며 앱 `ingress`(`deploy/shared/ingress`)가 소유 |
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
| `scripts/00`~`05` 실행 파일 | Make 단계별 명령의 진입점. `keycloak-setup`은 `00`~`03`을 순서대로 실행하고 CSV가 있으면 `05`도 실행 |
| `scripts/admin_env.py` | 관리 API 도구에 env의 관리자 계정을 환경변수로 전달. `KEYCLOAK_ADMIN_URL`·`USERNAME`·`PASSWORD` 중 하나라도 직접 지정하면 전달하지 않음 |
| `scripts/init_sdwt.py` | `/org` 소속 그룹·사용자 등록과 공통 scope 연결. 적용 시 `org_sync.py`도 실행 |
| `scripts/org_sync.py` | `keycloak-org-sync`의 소속별 역할·라인/팀 묶음·`org-claims` scope 반영. [소속별 역할](02-configure.md#소속별-역할) |
| `scripts/access_apply.py` | `keycloak-access-apply`의 앱 역할·기본 역할·Etch Members 카탈로그 반영 |

설정 Job은 선택한 context에 관리 ConfigMap `keycloak-claim-mapper`를 적용한 뒤 실행합니다.
프로필 단계는 `KEYCLOAK_PROFILE_ONLY=true`, 수신 mapper 단계는 `KEYCLOAK_SKIP_PROFILE=true`로 같은 Job 원본을 구분합니다.
Portal client Job은 `deploy/portal/k8s/jobs/keycloak-client`가 소유합니다.

### 배포 명령의 처리 범위

| 명령 | 처리 범위 |
| --- | --- |
| `keycloak-check` | env·공용 TLS 등록·manifest·기존 Secret·PV/PVC·공용 Traefik 존재·worker 상태를 조회하고 검사. 클러스터 변경 없음. 성공: `Keycloak 입력·원본·기존 Secret·worker 검사 통과. 클러스터를 변경하지 않았습니다.` |
| `keycloak-up` | 같은 검사 뒤 없는 namespace·runtime Secret 생성, 새 PV일 때 DB 폴더 준비 Job, PostgreSQL·Keycloak 적용 후 rollout 대기(각 600초). 공용 Traefik은 있는지와 공용 TLS를 읽는지만 확인하고 설치·갱신하지 않음. 성공: `Keycloak 배포 완료: <공개 URL>` |
| `keycloak-setup` | 입력 검사 → Realm → 사내 IdP → User Profile → IdP mapper Job → 입력 CSV 적용. [설정 단계와 Job](02-configure.md#설정-단계와-job) |
| `keycloak-smoke` | 워크로드 Ready와 공개 주소의 discovery 응답을 조회 |

최초 기동 시 관리자 계정을 만들고 이후 설정 Job도 같은 runtime Secret으로 로그인합니다.
`etch-sso` namespace가 없을 때만 원본의 label·annotation으로 생성하며, 이미 있으면 namespace 설정은 변경하지 않습니다.

| 선택 입력 | 사용하는 경우 |
| --- | --- |
| `KEYCLOAK_ENV=/절대/경로/prod.env` | 다른 env 파일 사용. 모든 명령에 동일하게 전달 |
| `KEYCLOAK_CERTS=/인증서/폴더` | `keycloak-check`·`keycloak-up`이 해당 폴더의 `fullchain.crt`·`private.key`를 검사하고 `keycloak-up`이 공용 TLS에 함께 등록한 뒤 Traefik을 다시 시작. 지정하지 않으면 이미 등록된 인증서를 검사만 함 |

공용 Traefik의 설치·갱신과 VIP backend 배치(`VIP_BACKENDS`)는 Keycloak 배포의 입력이 아닙니다. [ingress 가이드](../../shared/ingress/README.md)가 다루며 Keycloak·DB의 전용 Worker 조건은 Keycloak 원본에서 별도로 유지합니다.
Traefik이 없으면 검사·배포가 `공용 Traefik이 없습니다. make ops-deploy APP=ingress를 먼저 실행하세요.`로 끝납니다.

## Secret 불일치와 기존 DB 복구

배포 도구는 PV의 `claimRef`를 지우거나 데이터·namespace·PVC·Secret을 삭제하지 않고, 기존 Secret을 덮어쓰지 않습니다. 이 절의 오류는 보존된 DB와 맞지 않는 값으로 배포하는 것을 막는 검사입니다. 검사를 통과시키려고 Secret·PV·PVC를 바꾸지 않습니다.

### 기존 Secret과 env가 다른 경우

`keycloak-up`은 `keycloak-runtime` Secret이 없을 때만 만듭니다. 기존 Secret과 env가 다르면 검사·배포 모두 `keycloak-runtime: 기존 Secret과 입력이 다릅니다`로 중단합니다.
DB·관리자 비밀번호는 env와 Secret만 바꾼다고 실제 서비스의 값이 바뀌지 않습니다. 기존 Secret은 운영 중인 DB를 만든 값이므로 env를 기존 값에 맞추는 것이 조치입니다.

[조회] 먼저 어느 키가 다른지 확인합니다. 값은 출력하지 않습니다. 저장소 밖 env를 쓰면 끝의 env 경로를 그 파일로 바꿉니다.

```bash
kubectl --context "<context>" -n etch-sso get secret keycloak-runtime -o json | python3 -c '
import base64, json, sys
secret = json.load(sys.stdin).get("data", {})
env = dict(line.split("=", 1) for line in open(sys.argv[1]).read().splitlines() if "=" in line and not line.lstrip().startswith("#"))
for key in ("postgres-password", "bootstrap-admin-username", "bootstrap-admin-password", "keycloak-public-url"):
    same = base64.b64decode(secret.get(key, "")).decode() == env.get(key)
    print(key, "일치" if same else "불일치")
' deploy/keycloak/env/prod.env
```

성공: 키마다 `일치` 또는 `불일치`가 한 줄씩 출력됩니다. `keycloak-public-url`만 `불일치`이고 공개 주소 변경을 요청받았으면 [공개 인증 주소 변경](#공개-인증-주소-변경)을 따릅니다.

[검사] 그 밖의 경우에는 이 서버가 저장소 밖 env를 쓰는지 확인합니다. [운영 위치](../../shared/docs/infrastructure/operations.md#운영-파일과-데이터-위치)의 `관리 호스트 외부 앱 설정` 폴더에 Keycloak env가 있으면 그 경로로 다시 검사합니다.

```bash
make keycloak-check KUBE_CONTEXT="<context>" KEYCLOAK_ENV="<env 절대 경로>"
```

성공: `Keycloak 입력·원본·기존 Secret·worker 검사 통과`. 통과하면 이후 모든 Keycloak 명령에 같은 `KEYCLOAK_ENV`를 붙입니다.

그 뒤에도 같은 오류면 멈추고 위 조회의 키별 결과와 함께 보고합니다. Secret을 삭제하거나 다시 만들지 않고, DB·관리자 비밀번호를 재생성하지 않습니다. `make k8s-env APP=keycloak ...`은 기존 Secret을 덮어쓰므로 실행하지 않습니다. 다시 시작할 수 있는 조건은 기존 Secret과 같은 값을 가진 env이며 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일) 절의 방법으로 준비합니다.

### 기존 DB·namespace를 복구하는 경우

`keycloak-runtime`이 없고 DB의 PVC 또는 PV가 남아 있으면 검사·배포 모두 `기존 PVC가 있으나 keycloak-runtime이 없습니다`(PVC가 없으면 `기존 PV가 …`)로 적용 전에 중단합니다.
PV가 `Available`이어도 디스크가 비어 있다고 단정할 수 없으므로 같은 규칙을 적용합니다.
namespace 삭제로 PVC·Secret이 사라져도 `Retain` PV와 Worker의 DB 파일은 남을 수 있습니다.

[조회] 바인딩 상태를 확인합니다.

```bash
kubectl --context "<context>" get pv keycloak-postgres-data \
  -o jsonpath='{.status.phase}{"\n"}{.spec.claimRef}{"\n"}'
kubectl --context "<context>" -n etch-sso get pvc keycloak-postgres-data \
  -o jsonpath='{.metadata.uid}{"\n"}'
```

이 상태에서는 멈추고 위 조회 결과(PV의 phase와 `claimRef`, PVC UID)를 보고합니다. PV·PVC·`claimRef`·namespace·Worker의 DB 폴더를 지우거나 고치지 않고, 새 값으로 `keycloak-runtime`을 만들지 않습니다. 새 비밀번호로 만든 Secret은 보존된 DB와 맞지 않습니다.

다시 시작할 수 있는 조건은 다음 두 가지입니다. 둘 다 확인되면 `make keycloak-check KUBE_CONTEXT="<context>"`부터 다시 실행합니다.

- `keycloak-runtime`이 기존 DB를 만든 비밀번호·관리자 설정으로 복원돼 있음
- PV가 `Released`가 아니고 현재 PVC를 참조함. PV가 `Released`이거나 이전 PVC의 UID를 참조하면 runtime Secret을 복원했어도 배포는 중단됩니다

## 공개 인증 주소 변경

[승인] Keycloak 공개 주소와 issuer를 바꿉니다. 로그인 서비스가 재시작되고 모든 앱의 issuer가 함께 바뀌어야 하므로 주소 변경을 요청받았을 때만 수행합니다. 새 주소와 영향받는 앱(Portal·Airflow·Headlamp·API server OIDC)을 보여 주고 승인받은 뒤 아래 단계를 진행합니다.
운영 공개 주소는 `https://sso.etch.samsungds.net`, realm issuer는 `https://sso.etch.samsungds.net/realms/etch`입니다.
테스트 SSO 주소 계획은 [네트워크 정보](../../shared/docs/infrastructure/network.md)를 따르며 이 절차로 별도 테스트 SSO를 만들지 않습니다.

| 준비물 | 준비 방법과 확인 |
| --- | --- |
| 새 이름의 DNS → APP VIP | [DNS](../../shared/docs/infrastructure/access.md#dns) 절. `getent hosts <새 host>` |
| 새 이름이 SAN에 있고 CA 체인·만료를 확인한 인증서 | [인증서 발급](../../shared/docs/infrastructure/access.md#인증서-발급) 절 |
| 기존 credential과 일치하고 `keycloak-public-url`만 새 주소인 env | [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 복사본에서 `keycloak-public-url` 한 줄만 새 주소로 바꿈 |
| Ingress host가 새 주소인 저장소 원본 | Ingress host는 `k8s/server/stack.yaml`에 있어 checkout 갱신으로만 바뀜. 3단계의 검사가 `공개 URL과 Keycloak Ingress 도메인이 다릅니다`로 끝나면 원본이 아직 이전 주소이므로 멈추고 보고하며 원본을 직접 고치지 않음 |

앱 callback 경로·client ID·secret·계정·권한·realm·DB·namespace와 내부 Service 주소는 유지합니다.
명령은 관리 호스트의 저장소 루트에서 실행합니다. 외부 env 파일을 쓰면 아래 명령의 env 경로를 그 파일로 바꾸고 Make 명령에 `KEYCLOAK_ENV="<env 절대 경로>"`를 붙입니다.

### 1. 인증서와 AD FS 준비

[변경] 새 도메인 인증서를 [공용 TLS 등록](../../README.md#공용-tls-등록)의 명령으로 먼저 등록합니다. 성공: `공용 TLS 등록 완료: <새 host>`.
[변경] [AD FS](../../shared/docs/infrastructure/access.md#ad-fs) 절의 방법으로 새 broker redirect URI(`<새 공개 URL>/realms/etch/broker/oidc/endpoint`)를 등록합니다. 등록 결과는 5단계의 사내 로그인으로 확인합니다.

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

성공: `Keycloak 입력·원본·기존 Secret·worker 검사 통과. 클러스터를 변경하지 않았습니다.`

[승인] 배포하고 Keycloak을 재시작합니다.

```bash
make keycloak-up KUBE_CONTEXT="<context>"
kubectl --context "<context>" -n etch-sso rollout restart deployment/keycloak
kubectl --context "<context>" -n etch-sso rollout status deployment/keycloak --timeout=10m
```

성공: `Keycloak 배포 완료: <새 공개 URL>`과 `deployment "keycloak" successfully rolled out`.

### 4. 앱 issuer 반영

[변경] Portal·Airflow·Headlamp의 운영 env와 실제 배포 입력의 issuer를 새 주소로 맞추고 각 앱 가이드의 `B. 업데이트`로 반영합니다. 결과는 앱별 `make <app>-smoke KUBE_CONTEXT="<context>"`로 확인합니다.
realm에 별도의 Frontend URL을 지정했다면 새 공개 주소와 일치하는지 [Keycloak 관리 API](../../shared/docs/infrastructure/access.md#keycloak-관리-api) 절의 방법으로 확인합니다.
[승인] API server OIDC가 구성되어 있다면 [모든 API server의 issuer와 CA](../../shared/docs/kubernetes/oidc.md)를 맞춥니다. API server가 다시 시작되므로 그 문서의 승인 단계를 따릅니다.

### 5. 확인

[조회] [가이드의 배포 후 확인](../README.md#c-배포-후-확인)을 실행하고, discovery 응답에서 issuer와 endpoint가 새 공개 주소인지 확인합니다.

```bash
curl -fsS <새 공개 URL>/realms/etch/.well-known/openid-configuration
```

성공: JSON의 `issuer`가 `<새 공개 URL>/realms/etch`입니다.

새 토큰의 issuer, AD FS 사내 로그인, 각 앱의 로그인·로그아웃, Headlamp 자원 조회까지 성공해야 완료입니다. [화면 기능 확인](../../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인하고, 확인하지 못한 시나리오를 완료로 보고하지 않습니다.
