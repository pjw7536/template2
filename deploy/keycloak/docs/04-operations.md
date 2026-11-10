# CP1에서 Keycloak 배포 파일 관리

[Keycloak 시작 안내](../README.md) · [CP1 공통 Git·파일 관리](../../shared/docs/operations/01-checkout.md#git운영-파일-관리)

CP1은 배포 명령을 실행하는 호스트이며 Keycloak·PostgreSQL은 manifest에 지정한 Worker에서 실행됩니다.
저장소를 갱신하는 것과 Kubernetes·사용자 설정을 적용하는 것은 별개의 작업입니다.

최초 설치 명령은 [서버 준비](01-prepare.md#서버-준비)·[서버 배포](02-deploy.md)와 [Keycloak 자체 설정](03-configure.md#realm과-사내-로그인)에만 둡니다.

## 파일 소유 위치

| 내용 | 원본 위치 |
| --- | --- |
| 서버·노드·PV/PVC | `deploy/keycloak/k8s/server/` |
| 사내 IdP·프로필·mapper | `deploy/keycloak/k8s/oidc/`, `deploy/keycloak/k8s/claims/` |
| 설정 실행 | `deploy/keycloak/scripts/` |
| 등록 CSV 양식 | `deploy/keycloak/inputs/` |
| 서버·사내 IdP 설정값 | `deploy/keycloak/env/prod.env` |
| 사이트 인증서 | `deploy/shared/certs/`의 Keycloak 도메인 폴더 |
| PostgreSQL 실제 데이터 | Worker local PV 경로. Git checkout에 포함되지 않음 |

## 저장소 갱신 후 반영

[CP1 공통 안내](../../shared/docs/operations/01-checkout.md#git운영-파일-관리)에 따라 브랜치·변경사항을 확인하고 pull합니다.
그다음 변경 종류에 맞는 Keycloak 소유 안내를 사용합니다.

| 변경 내용 | 확인할 안내 |
| --- | --- |
| 문서만 변경 | 서버 적용 불필요 |
| 서버 manifest | [서버 검사·배포](02-deploy.md#3-검사-후-서버-배포) |
| IdP·프로필·수신 mapper | [설정 단계와 Job 결과](03-configure.md#realm과-사내-로그인) |
| 인증서 | [TLS 참고](01-prepare.md#tlsca-준비), 공용 인증서 안내의 Secret 갱신 절차 |
| Portal·Headlamp client | [앱 연결](03-configure.md#앱-연결) 및 해당 앱의 소유 문서 |

DB·관리자 비밀번호는 env와 Secret만 바꾼다고 실제 서비스의 값이 바뀌지 않습니다.
설정 불일치가 발견되면 실제 값과 원본을 먼저 확인합니다.

## 외부 env 파일을 사용하는 환경

기본 입력은 저장소의 `deploy/keycloak/env/prod.env`입니다.
외부 파일을 사용하도록 구성한 서버에서는 검사와 적용에 **같은 파일 경로**를 전달합니다.
설정을 두 곳에 중복 관리하지 않습니다.

```bash
read -r -p '대상 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
read -r -p 'Keycloak env 절대 경로: ' KEYCLOAK_ENV_PATH
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
```

배포 시에도 `keycloak-up`에 같은 `KUBE_CONTEXT`, `KEYCLOAK_ENV`를 지정합니다.
사내 IdP 단계는 `keycloak-idp-setup`에 같은 경로를 전달합니다.

사이트 인증서는 공용 TLS 등록 명령으로 관리합니다. `KEYCLOAK_CERTS`는 명시한 PEM을 공용 저장소에 가져오는 선택적 호환 입력입니다.

## 공개 인증 주소 반영

운영 공개 주소는 `https://sso.etch.samsungds.net`, realm issuer는
`https://sso.etch.samsungds.net/realms/etch`입니다. DNS 변경은 사용자가 직접 수행합니다.
실제 DNS·VIP 경로와 새 이름의 SAN·CA 체인·만료를 확인하고 [공용 TLS 등록](../../shared/docs/certificates/apply.md)을 먼저 마칩니다.
AD FS에 [새 복귀 주소](03-configure.md#2-사내-identity-provider-생성)도 등록합니다.

최초 설치는 새 `keycloak-public-url`이 들어 있는 env로 [검사·배포](02-deploy.md#3-검사-후-서버-배포)를 진행합니다.
기존 `keycloak-runtime` Secret이 있으면 배포 도구는 env와 불일치할 때 중단합니다.
이때 Secret을 삭제하거나 DB·관리자 비밀번호를 재생성하지 않습니다.
기존 credential과 일치하는 env를 준비하고 `keycloak-public-url`만 새 주소로 맞춥니다.

아래 명령은 **기존 Secret이 있을 때만**, 앞 절에서 선택한 동일 context·env로 CP1에서 실행합니다.
Secret의 공개 URL 항목만 갱신하며 비밀번호·다른 키는 변경하거나 출력하지 않습니다.

```bash
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
make keycloak-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_ENV="$KEYCLOAK_ENV_PATH"
```

검사가 통과한 뒤 `make keycloak-up`에 같은 context·env를 전달합니다.
기존 Pod는 Secret의 env 변경만으로 재시작되지 않으므로 다음을 실행합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout restart deployment/keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso rollout status deployment/keycloak --timeout=10m
```

Portal·Airflow·Headlamp의 운영 env와 실제 배포 입력의 issuer를 새 주소로 맞추고 해당 앱의 절차로 반영합니다.
앱 자체 callback 경로·client ID·secret·계정·권한·realm·DB·namespace와 내부 Service 주소는 유지합니다.
realm에 별도의 Frontend URL을 지정한 경우에도 새 공개 주소와 일치하는지 확인합니다.
Headlamp용 API server OIDC가 구성되어 있다면 [모든 API server의 issuer와 CA](../../headlamp/docs/02-authentication.md#api-server-인증)를 맞춥니다.

적용 후 [Discovery 조회](02-deploy.md#4-서버-기동-확인)의 issuer와 endpoint가 새 공개 주소인지 확인합니다.
새 토큰의 issuer, AD FS 사내 로그인, 각 앱의 로그인·로그아웃, Headlamp 자원 조회까지 성공해야 합니다.
테스트 `sso.stg.etch.samsungds.net`은 주소 계획이며 이 절차로 별도 테스트 SSO를 생성하지 않습니다.

## 전달용 YAML

`rendered/`는 [Kubernetes 원본 참고](05-reference.md#kubernetes-원본)의 별도 전달 파일입니다.
일반 설치는 단계별 Make 명령을 사용합니다.

전달 스택에는 Headlamp namespace 권한·ingress 노드 라벨 등 별도 조건이 있습니다.
공용 라우팅이 연결된 서버에 직접 적용하면 감시 범위·배치가 원본 값으로 바뀔 수 있습니다.
