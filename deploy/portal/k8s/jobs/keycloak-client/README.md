# Portal의 Keycloak client 등록

[Portal 배포 안내](../../../README.md)

이 Job은 Portal 소유의 `deploy/portal/env/prod/api.env`에서 필요한 로그인 설정만 받아,
Keycloak의 `etch` realm에 client와 18개 token mapper를 생성하거나 갱신합니다.
실행 위치는 Keycloak이 있는 `etch-sso` namespace입니다. Portal API가 아직 없어도
실행할 수 있지만, 공개 Portal URL과 callback은 실제 사용할 값으로 지정해야 합니다.

## 사전 준비

- 최신 `internal-keycloak-claim-mappers.yaml`로 프로필과 IdP mapper 작업을 먼저 완료합니다. 이 파일이 공통 관리 스크립트 ConfigMap도 준비합니다.
- `keycloak-runtime`의 관리자 계정이 실제 Keycloak 관리자 계정과 일치해야 합니다.
- `deploy/portal/env/prod/api.env`을 참고해 `OIDC_PROVIDER`, `OIDC_CLIENT_ID`,
  `OIDC_CLIENT_SECRET`, `OIDC_ISSUER`, `OIDC_REDIRECT_URI`, `FRONTEND_BASE_URL`을 작성합니다.
- 기존 파일이 있다면 예시로 덮어쓰지 않습니다. DB 항목은 client 등록 단계에서는 필수가 아닙니다.

## 실행

```bash
make env-check APP=portal PROFILE=prod COMPONENT=client
make k8s-env APP=portal PROFILE=prod COMPONENT=client
kubectl delete job portal-keycloak-client -n etch-sso --ignore-not-found
kubectl apply -k deploy/portal/k8s/jobs/keycloak-client
kubectl wait --for=condition=complete job/portal-keycloak-client -n etch-sso --timeout=15m
kubectl logs job/portal-keycloak-client -n etch-sso
```

같은 client ID가 있으면 해당 client의 secret, callback 목록, Web origin, PKCE와 logout
설정을 입력값에 맞춥니다. 추가 callback을 관리 화면에 등록했던 경우 목록이 이 파일의
callback 하나로 바뀌므로 먼저 확인합니다. 다른 client나 사내 OIDC 접속 정보는 바꾸지 않습니다.
Portal API에도 동일한 `api.env`를 적용해야 client secret이 일치합니다.

16개 token claim은 ID Token, Access Token, UserInfo에 기존 사내 claim 이름의 문자열로 포함합니다.
예: `display_name → username`, `knox_id → loginid`, `department → deptname`. 기본
`username → userid`, `email → mail`은 사용자 property mapper로 처리합니다.
`firstName → givenname`, `lastName → surname`도 기본 사용자 property에서 읽습니다.
사내 claim 이름은 유지하며 커스텀 `givenname`·`surname` 속성은 더 이상 읽지 않습니다.
기존 `first_name`·`last_name` token mapper는 제거합니다. 이 client Job은 Keycloak 로그인 ID를 변경하지 않습니다. EPID username은
IdP Job의 `epid-username` mapper가 사내 재로그인 때 반영합니다. 사내 OIDC에서
사용자 속성을 가져오는 mapper는 Keycloak의 별도 claim Job이 설정합니다. 새 사용자는
사내 OIDC 로그인 후에 속성이 채워집니다.

서버 스택이나 Portal 앱 overlay만 적용하면 두 mapper Job은 자동 실행되지 않습니다.
사내 OIDC → Keycloak의 16개 속성은 [Keycloak 안내 7절](../../../../keycloak/README.md)의
`keycloak-oidc-claim-mappers` Job을, Keycloak → Portal의 16개 token claim은 위의
`portal-keycloak-client` Job을 실행하고 각각 완료 로그를 확인합니다. 이미 완료된 Job도
스크립트나 정책을 바꿨다면 최신 ConfigMap 적용 후 삭제·재생성해야 합니다.

## 단일 파일로 전달

Portal 연결이 필요할 때 개발 PC에서 다음 명령으로 전달 파일을 생성합니다.

```bash
kubectl kustomize deploy/portal/k8s/jobs/keycloak-client > /tmp/internal-portal-keycloak-client.yaml
```

생성된 파일을 CP1에 전달합니다. 위 apply 대신 `kubectl apply -f internal-portal-keycloak-client.yaml`을
사용합니다. Secret 입력은 별도로 등록해야 합니다. 운영 서버에 Bash와 kubectl만 있으면
실행되며 Node.js는 테스트할 때만 필요합니다.

직급은 `grdName → grd_name → grdName` 매핑을 복원하며 `grdname_en`도 유지합니다.
`origincomp`는 계속 프로필에서 제외하고 각 Job이 기존 mapper를 삭제합니다.
기존 사용자 속성값과 Django DB 컬럼은 일괄 삭제하지 않습니다.
직급 반영은 두 Job을 재실행하고 사내 재로그인한 뒤 확인합니다.

`userid` token mapper는 Keycloak 기본 `username`의 EPID를 읽습니다. Keycloak의 커스텀
`avatarid`는 사용하지 않습니다. 기존 계정은 사내 재로그인으로 username을 먼저 갱신합니다.

## 실제 소속 claim

사내 claim 16개와 별도로 `user_sdwt_prod`, `line_id`를 단일 문자열로 발급합니다.
동일 이름의 사용자 속성을 User Attribute mapper로 읽어 ID Token·Access Token·UserInfo에 포함하며,
값이 없으면 생략합니다. 두 속성은 Keycloak claim Job으로 먼저 정의하고 관리자 또는 EPID 기반
참조 테이블 동기화가 채웁니다. 사내 IdP 수신 mapper는 만들지 않습니다.
두 값만으로 권한을 부여하지 않으며 그룹 권한과 구분합니다. Django의 기존 소속 모델·판정은
아직 전환하지 않았으므로 이 claim 추가만으로 Django 소속이 자동 갱신되지는 않습니다.
