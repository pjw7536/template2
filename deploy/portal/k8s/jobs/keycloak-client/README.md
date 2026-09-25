# Portal 최초 Keycloak 연결

[Portal 배포 안내](../../../README.md) · 선행 조건: [Keycloak 설정 완료](../../../../keycloak/04_SETUP_FLOW.md#설정-완료-확인)

Keycloak 자체 설정과 사내 시험 로그인을 마친 뒤 Portal 전용 client·token mapper를 등록합니다.
공개 Portal URL과 callback은 실제 사용할 값으로 정합니다.

## 입력 준비

저장소 루트의 Bash에서 실행합니다.

```bash
kubectl config current-context
kubectl config get-contexts
read -r -p 'Keycloak이 설치된 Kubernetes context: ' KEYCLOAK_KUBE_CONTEXT
vi deploy/portal/env/prod/api.env
```

`OIDC_PROVIDER=keycloak`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`,
`OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`을 입력합니다.
사내 AD FS client와 별개의 Portal 전용 ID·secret을 사용합니다.
issuer는 Keycloak `etch` realm의 discovery에 나온 값과 같아야 합니다.

## client 등록

```bash
make keycloak-portal-client-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/portal-keycloak-client
```

명령은 입력 검사·관리 ConfigMap·client Secret 준비 후 Job을 실행하고 완료를 기다립니다.
사내 IdP·User Profile·수신 mapper는 이 단계에서 설정하지 않습니다.

사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 발급합니다.
전체 필드는 [claim 매핑 계약](../../../../keycloak/06_CLAIMS.md)을 따릅니다.
SDWT 그룹을 발급하려면 [앱 그룹 연결](../../../../keycloak/09_APP_CONNECTIONS.md#sdwt-그룹을-portal에-전달하는-경우)을 수행합니다.

## Portal 배포와 확인

같은 `api.env`를 사용해 [Portal 배포 안내](../../../README.md)에 따라 API Secret·앱을 배포합니다.
이 client 등록 명령만으로 Portal API가 배포되지는 않습니다.
시험 계정으로 로그인해 callback, 신원 claim, 필요한 소속·그룹과 앱 접근 판정을 확인합니다.
Keycloak의 소속·그룹을 발급하는 것과 Portal의 실제 권한 판정 구현은 별개입니다.
