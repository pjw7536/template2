# Discovery로 사내 로그인 전체 설정

`CORP_OIDC_DISCOVERY_URL`을 env로 입력하면 기존 Job을 이용해 다음 순서로 설정합니다.

```text
Discovery 검증 → OIDC Secret → 관리 ConfigMap → Identity Provider 생성/갱신
  → 사용자 프로필 및 16개 IdP mapper → [선택] Portal client 및 18개 token mapper
  → 시험 계정 로그인 검증
```

## 1. 발급 정보와 실행 환경 준비

- 먼저 `make keycloak-up`으로 Keycloak과 realm `etch`를 준비합니다.
- 실행 호스트에 Python 3, Bash, kubectl과 대상 클러스터 권한이 필요합니다. 호스트에서 discovery에 접근 가능해야 하며 사내 CA가 필요하면 `SSL_CERT_FILE`로 신뢰 CA 파일을 지정합니다.
- Keycloak 서버도 token, JWKS, UserInfo endpoint에 접근하고 인증서를 신뢰해야 합니다. 호스트의 TLS 설정이 Keycloak에 자동 전파되지는 않습니다.
- AD FS에 Authorization Code용 client ID·secret을 발급받고 callback을 `${공개 Keycloak URL}/realms/etch/broker/oidc/endpoint`로 정확히 등록합니다. Portal callback과는 다른 주소입니다.
- 발급된 client의 인증 방식(`client_secret_post` 또는 `client_secret_basic`)을 확인합니다. Discovery의 지원 목록만으로 개별 client의 인증 방식을 결정할 수는 없습니다.

## 2. env 입력

`deploy/keycloak/env/prod.env`에는 discovery URL과 인증 방식이 이미 설정돼 있습니다.
기존 provider의 client ID·secret을 입력합니다. 다른 환경에서는 discovery URL도 해당 환경에 맞춥니다.
값은 전달받은 OpenID Connect 1.0 discovery endpoint를 그대로 사용합니다. 사내 주소는 코드에 고정하지 않습니다.

```dotenv
CORP_OIDC_DISCOVERY_URL=<전달받은 discovery URL>
CORP_OIDC_CLIENT_ID=<AD FS에서 발급한 client ID>
CORP_OIDC_CLIENT_SECRET=<AD FS에서 발급한 secret>
CORP_OIDC_CLIENT_AUTH_METHOD=client_secret_post
CORP_OIDC_VALIDATE_SIGNATURE=true
```

이 흐름은 authorization/token/issuer/JWKS 값을 metadata에서 가져옵니다.
현재 provider의 `Client secret sent in the request body`는 `client_secret_post`에 해당합니다.
운영 env에서는 discovery로 확인 가능한 URL·issuer 6개 항목을 제거했으므로 따로 작성하지 않습니다.
기존 env의 해당 endpoint보다 discovery 값을 우선하며 원본 env는 덮어쓰지 않습니다.
issuer는 AD FS가 반환한 값을 그대로 보존합니다. 통신 endpoint는 HTTPS만 허용합니다.
UserInfo/logout은 metadata에 있으면 사용하고 없으면 기존 env 값을 사용합니다.
둘 다 없으면 기존 IdP의 해당 설정을 보존하므로, 서버 이전 시에는 관리 화면에서 잔존 URL도 확인합니다.
Discovery 지원 인증 방식이 생략되면 OIDC 기본값인 `client_secret_basic`으로 검사합니다.
이 실행 흐름은 서명 검증을 반드시 켜고 JWKS를 요구합니다.

Discovery는 client 등록, 사내 claim 발급 정책, 그룹 권한을 자동 결정하지 않습니다.
`claims_supported` 목록만으로 mapper를 생성하지 않고 저장소의 기존 계약을 적용합니다.

## 3. 검사 후 적용

저장소 루트에서 실행합니다. context를 명시해야 하며 현재 kubectl context는 바뀌지 않습니다.

```bash
make keycloak-oidc-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
make keycloak-oidc-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT"
```

`make env-check APP=keycloak PROFILE=prod COMPONENT=oidc`와
`make k8s-env APP=keycloak PROFILE=prod COMPONENT=oidc`도 같은 discovery 해석기를 사용하지만
각각 입력 검사·Secret 등록만 수행합니다. Job 실행까지는 위의 통합 명령을 사용하세요.

별도 env는 `KEYCLOAK_ENV=/절대/경로/keycloak.env`로 지정합니다.
`check`는 metadata와 입력 검증이며 클러스터·실제 로그인 성공을 보장하지 않습니다.
`setup`은 `etch-sso`의 Secret 및 설정 Job만 적용하며 서버 스택은 배포하지 않습니다.
IdP alias는 기존 `oidc`를 사용합니다. 기존 사용자를 삭제하거나 자동 계정 연결 정책을 변경하지 않습니다.
신규 IdP는 기본 first broker login 정책과 `openid` scope를 사용합니다.

Portal까지 연결하려면 Portal client 발급 입력도 함께 지정합니다.

```bash
make keycloak-oidc-check KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
make keycloak-oidc-setup KUBE_CONTEXT="$KEYCLOAK_KUBE_CONTEXT" KEYCLOAK_PORTAL_ENV="$PWD/deploy/portal/env/prod/api.env"
```

Portal은 별도의 Keycloak client입니다. AD FS client secret을 재사용하지 않습니다.
Portal env에 필요한 항목과 callback 갱신 범위는 [client 등록 계약](../portal/k8s/jobs/keycloak-client/README.md)을 따릅니다.
Portal 옵션을 사용하려면 해당 deploy 경로도 checkout해야 합니다. Portal API의 env 적용·배포는 해당 앱 배포 절차로 수행합니다.

## 4. Mapper 및 로그인 확인

1. Admin Console의 `etch → Identity providers → oidc`에서 issuer, endpoint, JWKS 및 client 인증 방식을 확인합니다.
2. Mappers에 일반 속성 15개와 `epid-username`이 있는지 확인합니다. `userid`(EPID)는 기본 username, `loginid`는 `knox_id`, `mail`은 email, `givenname`/`surname`은 기본 이름에 저장합니다. 전체 매핑은 [Keycloak 7절](README.md#7-사내-oidc-사용자-claim-일괄-매핑)을 따릅니다.
3. 시험 계정으로 사내 로그인을 수행해 실제 claim 발급을 확인합니다. Discovery는 이 claim들의 존재·값을 보장하지 않습니다. EPID와 기존 계정이 다를 때 임의로 자동 연결하지 않고 기존 first broker login 절차로 확인합니다.
4. Portal 옵션을 사용했다면 Portal 로그인과 토큰의 `userid`, `loginid`, `mail` 등 기존 claim을 확인합니다. 프로필·mapper 설정만으로 기존 사용자 값이 채워지지 않으며 사내 재로그인이 필요합니다.
5. `user_sdwt_prod`, `line_id`는 사내 IdP에서 가져오지 않습니다. 소속·그룹 권한이 필요하면 [SDWT 초기 설정](SDWT_SETUP.md)을 따릅니다. Discovery로 권한을 추론하지 않습니다.

동기화는 기존 mapper의 `FORCE` 정책을 유지합니다. EPID 매핑을 위해 realm의 `Email as username`은 꺼져 있어야 하며 기존 Job이 이를 검사합니다.

## 실패 및 재실행

각 Job의 완료를 기다린 다음에만 다음 단계로 진행합니다. 실패 시 이미 완료한 변경은 유지되며 자동 롤백하지 않습니다.
입력을 수정한 뒤 같은 명령을 재실행하면 같은 alias와 mapper 이름을 갱신합니다.
동일 환경에서 이 명령을 동시에 실행하지 마세요. 기존 설정 Job을 삭제·재생성합니다.

```bash
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso get jobs
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-oidc-setup
kubectl --context "$KEYCLOAK_KUBE_CONTEXT" -n etch-sso logs job/keycloak-oidc-claim-mappers
```

Discovery는 명령 실행 시 다시 읽습니다. metadata의 endpoint 변경이 실행 사이에 자동 동기화되지는 않습니다. JWKS 키 갱신은 기존 Keycloak JWKS 처리를 사용합니다.

근거: [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker), [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).
