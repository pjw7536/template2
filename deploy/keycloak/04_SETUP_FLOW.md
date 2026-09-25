# 04. Keycloak 자체 설정

[전체 설치 순서](README.md) · 이전: [서버 설치](01_SERVER_SETUP.md) · 다음: [앱 연결](09_APP_CONNECTIONS.md)

서버 설치를 마친 뒤 Realm → 사내 IdP → User Profile → IdP mapper → 선택 SDWT 순서로 설정합니다.
여기서는 Portal·Headlamp client를 만들지 않습니다. 아래 명령은 하나씩 실행하고 성공을 확인한 뒤 다음 단계로 넘어갑니다.

## 실행 준비

서버 설치 때 사용한 저장소 루트의 Bash에서 실행합니다. 새 터미널이라면 저장소로 이동한 뒤
아래 context 선택을 다시 합니다. `NAME` 열의 실제 클러스터 이름을 입력합니다.

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p '설정할 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get deployment keycloak
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get secret keycloak-runtime
```

`keycloak-runtime`의 관리자 계정은 서버 설치 때 준비한 계정입니다.
각 Make 명령은 자신의 설정 Job을 생성하고 최대 15분 완료를 기다립니다. 별도로 Job을 apply할 필요는 없습니다.

## 1. Realm 준비

```bash
make keycloak-realm-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

Admin Console에 서버 설치 때 입력한 관리자 계정으로 접속하고 `etch` realm을 선택합니다.
서버 최초 import가 이미 `etch`를 만들었다면 이 명령은 존재 여부만 확인합니다.
이후 모든 관리 화면 설정은 `master`가 아닌 `etch`에서 확인합니다.

## 2. 사내 Identity Provider 생성

[환경변수 안내](env/02_ENVIRONMENT.md#사내-identity-provider용-값)에 따라
`deploy/keycloak/env/prod.env`의 사내 client ID·secret을 입력합니다.
AD FS의 redirect URI는 `<공개 Keycloak URL>/realms/etch/broker/oidc/endpoint`입니다.

```bash
vi deploy/keycloak/env/prod.env
python3 deploy/keycloak/scripts/setup_discovery.py check --step idp --context "$KEYCLOAK_KUBE_CONTEXT" --env deploy/keycloak/env/prod.env
```

검사가 통과한 뒤 적용합니다.

```bash
make keycloak-idp-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Identity providers → oidc`에서 연결이 생성됐는지 확인합니다.
Discovery 해석·인증 방식은 [05 Discovery 참고](05_DISCOVERY_SETUP.md)에 설명합니다.

## 3. User Profile 등록

```bash
make keycloak-profile-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Realm settings → User profile`에서 `loginid`, `deptname`, `grdName`, `display_name`, `sabun` 등을 확인합니다.
사용자는 본인 필드를 조회할 수 있고 편집은 관리자만 가능합니다. 전체 필드 정의는 [06 매핑 참고](06_CLAIMS.md)에 있습니다.

## 4. 사내 claim 수신 mapper 설정

`Realm settings`에서 `Email as username`이 꺼져 있는지 확인한 뒤 실행합니다.

```bash
make keycloak-idp-mappers-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`Identity providers → oidc → Mappers`에서 일반 속성 mapper 15개와 `epid-username` 1개를 확인합니다.
mapper 생성만으로 사용자 값이 채워지지는 않습니다. 사내 로그인을 거쳐야 수신합니다.

## 5. 소속·SDWT 그룹 초기 설정

SDWT 권한을 사용할 경우 [07 SDWT 설정](07_SDWT_SETUP.md)을 완료한 뒤 이 문서로 돌아옵니다.
그룹·사용자는 앱 client 없이 등록합니다. SDWT를 사용하지 않으면 이 단계는 생략합니다.

## 설정 완료 확인

Portal·Headlamp를 설치하기 전에 Keycloak 기본 Account Console로 사내 로그인을 확인합니다.
브라우저에서 아래 주소를 열고 사내 provider를 선택해 시험 계정으로 로그인합니다.

```text
<공개 Keycloak URL>/realms/etch/account/
```

Account Console 경로는 [Keycloak 공식 시작 안내](https://www.keycloak.org/getting-started/getting-started-kube)를 따릅니다.

| 확인 위치 | 완료 기준 |
| --- | --- |
| Account Console | 사내 인증을 거쳐 사용자 계정 화면에 도달 |
| Admin Console → Users → 시험 사용자 | 기본 username은 EPID, loginid·deptname·grdName 등 사내에서 제공한 값이 저장됨 |
| Users → 시험 사용자 → Identity provider links | 사내 `oidc` 연결 확인 |
| Groups / Users → Groups | SDWT 사용 시 준비한 그룹과 시험 사용자의 가입 확인 |

CSV로 사전 등록한 계정은 첫 사내 로그인에서 계정 연결 확인이 필요할 수 있습니다.
EPID가 같다는 이유만으로 자동 연결을 가정하지 않습니다. 시험 계정으로 연결이 완료되는지 확인합니다.
여기까지 완료하면 **Keycloak 자체 준비 완료**입니다. 다음은 [09 앱 연결](09_APP_CONNECTIONS.md)입니다.
앱의 토큰·로그인·권한 검증은 각 앱 연결 단계에서 수행합니다.

## Job 결과 확인

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
read -r -p '로그를 확인할 Job 이름: ' KEYCLOAK_JOB_NAME
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs "job/$KEYCLOAK_JOB_NAME"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso describe job "$KEYCLOAK_JOB_NAME"
```

| 작업 | 실행 파일 | Job 이름 |
| --- | --- | --- |
| Realm | `scripts/00-create-realm.sh` | `keycloak-realm-setup` |
| IdP | `scripts/01-create-idp.sh` | `keycloak-oidc-setup` |
| User Profile | `scripts/02-register-user-profile.sh` | `keycloak-user-profile-setup` |
| IdP mapper | `scripts/03-sync-idp-mappers.sh` | `keycloak-idp-mappers-setup` |
| SDWT | `scripts/05-setup-sdwt.sh` | Job 없이 관리자 API 사용 |

실행 파일 이름의 숫자는 유지하지만, 이 문서의 제목 순서대로 진행합니다.
Job 실패 시 로그의 원인을 해결하기 전 다음 단계로 넘어가지 않습니다.
