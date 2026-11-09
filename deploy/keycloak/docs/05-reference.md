# Keycloak 계약과 원본

[앱 안내](../README.md)

- [OIDC Discovery](#oidc-discovery)
- [사용자 필드와 claim](#사용자-필드와-claim)
- [Kubernetes 원본](#kubernetes-원본)

## OIDC Discovery

[전체 설치 순서](../README.md) · 실행 명령: [Keycloak 자체 설정](03-configure.md#2-사내-identity-provider-생성)

Discovery는 사내 IdP의 접속 정보를 자동으로 가져오는 기능입니다.
이 문서는 입력의 의미만 설명합니다. 실행 위치·context 선택·검사·적용은 위 실행 안내에서 한 번만 진행합니다.

### 자동으로 가져오는 값

실행 호스트가 `CORP_OIDC_DISCOVERY_URL`의 JSON을 조회하고 아래 정보를 IdP Job에 전달합니다.

| Metadata 항목 | 사용 목적 | 필수 여부 |
| --- | --- | --- |
| `authorization_endpoint` | 브라우저의 사내 인증 주소 | 필수 |
| `token_endpoint` | 인증 코드를 토큰으로 교환 | 필수 |
| `issuer` | 토큰 발급자 검증 | 필수 |
| `jwks_uri` | 서명 검증용 공개키 | 필수 |
| `userinfo_endpoint` | 사용자 정보 추가 조회 | 제공 시 사용 |
| `end_session_endpoint` | 사내 로그아웃 | 제공 시 사용 |

필수 값이 없으면 검사가 중단됩니다. 신규 IdP에 제공되지 않은 선택 URL은 추정해서 만들지 않습니다.
endpoint는 HTTPS를 사용하고 서명 검증은 활성화합니다. issuer는 받은 값을 그대로 사용합니다.

해석 결과는 임시 env와 Kubernetes Secret으로 전달하며 원본 `prod.env`를 덮어쓰지 않습니다.

### 별도로 준비하는 값

사내 client ID·secret은 AD FS에서 발급받아 [환경변수 안내](01-prepare.md#사내-identity-provider용-값)에 따라 입력합니다.
Discovery는 credential·사용자 claim 값·접근 권한을 발급하지 않습니다.

인증 방식 `client_secret_post`는 `Client secret sent in the request body`에 해당합니다.
metadata에 인증 방식 목록이 없으면 도구는 `client_secret_basic`을 기본 지원 방식으로 검사합니다.
이 경우 실제 client가 지원하는 인증 방식을 별도로 확인합니다.

### 네트워크와 인증서

- 실행 호스트: Discovery URL에 접근하고 CA를 신뢰해야 합니다. 별도 CA 파일은 `SSL_CERT_FILE`로 지정합니다.
- Keycloak Pod: 사내 Token·JWKS·UserInfo endpoint에 접근하고 CA를 신뢰해야 합니다.
- 브라우저: 사내 인증 주소와 공개 Keycloak 주소에 접근할 수 있어야 합니다.

호스트의 CA 신뢰가 Pod에 자동 전달되지는 않습니다. [TLS 준비](01-prepare.md#tlsca-준비)를 참고합니다.

참고: [OpenID Connect Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html).

## 사용자 필드와 claim

[전체 설치 순서](../README.md) · 실행: [Keycloak 자체 설정](03-configure.md#realm과-사내-로그인) · 발급 설정: [앱 연결](03-configure.md#앱-연결)

이 문서는 사내 사용자 정보가 Keycloak에 저장되고 앱 토큰으로 전달되는 규칙을 설명합니다.
프로필·수신 mapper 명령은 자체 설정 문서에서 실행합니다.

### 수신·저장·발급

```text
사내 AD FS claim → IdP mapper → Keycloak 사용자 필드 → 앱별 token mapper → 앱 토큰
```

커스텀 속성은 사내 claim 이름과 대소문자를 그대로 사용합니다.
아래 발급 열은 Portal 등록 도구가 만드는 계약입니다. 다른 앱에는 필요한 mapper를 별도로 설정해야 합니다.

| AD FS 수신 claim | Keycloak 내부 저장 필드 | 앱에 발급하는 claim |
| --- | --- | --- |
| loginid | loginid | loginid |
| userid (EPID) | username (기본 속성) | userid |
| username | display_name | username |
| deptname | deptname | deptname |
| mail | email (기본 속성) | mail |
| givenname | firstName (기본 속성) | givenname |
| surname | lastName (기본 속성) | surname |
| grdName | grdName | grdName |
| sabun | sabun | sabun |
| username_en | username_en | username_en |
| deptid | deptid | deptid |
| grdname_en | grdname_en | grdname_en |
| busname | busname | busname |
| intcode | intcode | intcode |
| intname | intname | intname |
| employeetype | employeetype | employeetype |

Keycloak 기본 `username`은 로그인 식별자인 EPID(`userid`)입니다.
사내 사람 이름 `username`은 충돌을 피하기 위해 `display_name`에 저장합니다.
이메일·성·이름은 기본 `email`·`firstName`·`lastName`을 사용합니다.

예를 들어 `userid=90000001`, `loginid=hong.gildong`, `username=홍길동`이면
내부에는 `username=90000001`, `loginid=hong.gildong`, `display_name=홍길동`으로 저장합니다.

### User Profile 권한

정의 원본은 [account-user-profile.json](../k8s/claims/account-user-profile.json)입니다.
프로필 필드는 본인·관리자가 조회하고 관리자만 편집합니다. 미정의 속성 정책은 `ADMIN_EDIT`입니다.
비밀번호·권한·로그인 시각은 커스텀 프로필에 복제하지 않습니다.

### IdP mapper

[수신 스크립트](../k8s/claims/sync-oidc-claim-mappers.sh)는 일반 속성 15개와 EPID mapper 1개를 등록합니다.
`epid-username`은 `${CLAIM.userid}`를 기본 username에 저장하는 Username Template Importer이며
`target=LOCAL`, `syncMode=FORCE`를 사용합니다.

EPID는 유일하고 변하지 않으며 재사용되지 않는 식별자여야 합니다. `Email as username`은 꺼야 합니다.

다른 수신 mapper도 `FORCE`를 사용하며 사내 인증을 거칠 때 값을 가져옵니다.
프로필 정의만으로 값이 생성되지 않으며 사내 응답에 해당 claim이 있어야 합니다.

### 소속과 권한

소속 정보와 접근 권한은 각각 관리합니다.

- 소속: `user_sdwt_prod`는 실제 소속 SDWT, `line_id`는 해당 line입니다. 관리자 또는 최초 CSV 등록으로 채우며 사내 IdP에서는 수신하지 않습니다.
- 접근 권한: `/{SDWT}/admin`, `/{SDWT}/user`, `/{SDWT}/viewer` 그룹으로 관리합니다. 소속이 바뀌어도 그룹을 자동으로 부여하지 않습니다.

초기 등록은 [SDWT 설정](03-configure.md#sdwt-그룹사용자), 앱의 `groups` 발급 연결은 [앱 연결](03-configure.md#앱-연결)에서 수행합니다.

### 앱 토큰 계약

Portal 도구는 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 단일 문자열로 발급하도록 설정합니다.
값이 없으면 해당 claim은 생략됩니다. SDWT 그룹을 연결하면 `groups`는 전체 경로의 문자열 배열입니다.
Portal DB 필드 이름과 Keycloak claim 이름은 별개의 계약입니다.

일반 신원 claim 전체를 공유하는 공통 Client Scope는 구현돼 있지 않습니다.
`sdwt-access-v1`은 그룹 발급용 scope이며 일반 신원 claim mapper를 대신하지 않습니다.
Headlamp는 별도 client의 그룹 mapper와 Kubernetes 권한 계약을 사용합니다.

## Kubernetes 원본

처음 설치할 때 manifest를 개별 적용할 필요는 없습니다.
[서버 준비·배포](../README.md)와 [Keycloak 설정](03-configure.md#realm과-사내-로그인)의 Make 명령이 아래 원본을 사용합니다.

### 원본과 역할

| 원본 | 역할 |
| --- | --- |
| `kustomization.yaml` | 서버·공용 ingress·관리 ConfigMap 구성 |
| `server/stack.yaml` | PostgreSQL·Keycloak·PV/PVC·Service |
| `server/etch-realm.json` | 최초 `etch` realm 정의 |
| `oidc/setup-realm.sh` | realm 준비 |
| `oidc/setup-oidc.sh` | 사내 IdP 연결 등록 |
| `oidc/oidc-setup-job.yaml` | IdP Job 원본, Realm Job에도 재사용 |
| `claims/account-user-profile.json` | 사용자 필드·조회/편집 권한 |
| `claims/sync-oidc-claim-mappers.sh` | 수신·발급 mapper 등록 |
| `claims/claim-mappers-job.yaml` | 프로필·mapper Job 원본 |
| `claims/sdwt-access-scope.json` | 앱 연결 시 사용하는 SDWT groups scope |

Traefik은 `deploy/shared/ingress`에서 참조합니다.
서버 배포는 관리 ConfigMap을 준비하지만 Realm·IdP·프로필·mapper 설정 Job을 실행하지 않습니다.
각 Job의 이름은 [설정 결과 확인](03-configure.md#job-결과-확인)에 있습니다.

### 도구의 실행 범위

`setup_discovery.py`가 명시한 context로 ConfigMap과 선택 단계의 Job을 준비합니다.
프로필 단계는 `KEYCLOAK_PROFILE_ONLY=true`, 수신 mapper 단계는 `KEYCLOAK_SKIP_PROFILE=true`로 구분합니다.
사내 접속 정보는 실행 호스트에서 Discovery를 조회한 뒤 Secret으로 전달합니다.

Portal client Job은 `deploy/portal/k8s/jobs/keycloak-client`가 소유합니다.
SDWT 초기 등록은 Job 대신 관리자 API를 사용합니다.

### 렌더 파일

`rendered/`에는 전달용으로 생성한 YAML을 보관합니다. 직접 편집하지 않습니다.

최초 설치에는 Python·Make를 사용하는 단계별 명령을 따릅니다.
전달용 YAML은 별도 배포 방식이므로 단계별 명령과 함께 적용하지 않습니다.
Headlamp namespace 감시·RBAC 등 별도 전제가 있어 최초 설치 명령을 대신할 수 없습니다.

### 관리 도구의 참조 관계

| 도구 | 호출 경로·역할 |
| --- | --- |
| `scripts/up.py` | `keycloak-check/up`의 서버 배포 구현 |
| `scripts/setup_discovery.py` | 단계별 실행 파일과 공통 env 도구의 Discovery 해석 |
| `scripts/00`~`05` 실행 파일 | Make 명령이 호출하는 단계별 진입점 |
| `scripts/init_sdwt.py` | SDWT 그룹·사용자 등록과 앱 scope 연결 |
| `scripts/render.sh` | `k8s-export`가 사용하는 전달 YAML 생성기 |
| `scripts/migrate_claim_attributes.py` | 별도 `keycloak-claim-attributes-migrate` 진입점. 최초 설치에는 사용하지 않음 |

통합 `keycloak-oidc-check/setup`과 전달용 `export/`는 기존 운영 절차에서 참조하므로 유지합니다.
최초 설치는 [설정 안내](03-configure.md#realm과-사내-로그인)의 단계별 명령만 사용합니다.

claim Job은 ConfigMap의 최신 스크립트를 직접 실행하며 임시 사본·realm 옵션 치환을 사용하지 않습니다.
