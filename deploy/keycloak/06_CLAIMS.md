# 06. 사용자 필드와 claim 매핑

[전체 설치 순서](README.md) · 실행: [Keycloak 자체 설정](04_SETUP_FLOW.md) · 발급 설정: [앱 연결](09_APP_CONNECTIONS.md)

이 문서는 필드 계약의 기준입니다. 프로필·수신 mapper 명령은 자체 설정 문서에서 실행합니다.

## 수신·저장·발급

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

## User Profile 권한

정의 원본은 [account-user-profile.json](k8s/claims/account-user-profile.json)입니다.
프로필 필드는 본인·관리자가 조회하고 관리자만 편집합니다. 미정의 속성 정책은 `ADMIN_EDIT`입니다.
비밀번호·권한·로그인 시각은 커스텀 프로필에 복제하지 않습니다.

## IdP mapper

[수신 스크립트](k8s/claims/sync-oidc-claim-mappers.sh)는 일반 속성 15개와 EPID mapper 1개를 등록합니다.
`epid-username`은 `${CLAIM.userid}`를 기본 username에 저장하는 Username Template Importer이며
`target=LOCAL`, `syncMode=FORCE`를 사용합니다. EPID는 유일하고 변하지 않으며 재사용되지 않는 식별자여야 합니다.
`Email as username`은 꺼야 합니다.

다른 수신 mapper도 `FORCE`를 사용하며 사내 인증을 거칠 때 값을 가져옵니다.
프로필 정의만으로 값이 생성되지 않으며 사내 응답에 해당 claim이 있어야 합니다.

## 소속과 권한

`user_sdwt_prod`는 실제 소속 SDWT, `line_id`는 해당 line입니다.
관리자 또는 최초 CSV 등록으로 채우고 사내 IdP에서는 수신하지 않습니다.
접근 가능한 SDWT는 별도 `/{SDWT}/admin`, `/{SDWT}/user`, `/{SDWT}/viewer` 그룹으로 관리합니다.
소속이 바뀌었다고 그룹을 자동으로 부여하지 않습니다.

초기 등록은 [07 SDWT 설정](07_SDWT_SETUP.md), 앱의 `groups` 발급 연결은 [09 앱 연결](09_APP_CONNECTIONS.md)에서 수행합니다.

## 앱 토큰 계약

Portal 도구는 사내 claim 16개와 소속 2개를 ID Token·Access Token·UserInfo에 단일 문자열로 발급하도록 설정합니다.
값이 없으면 해당 claim은 생략됩니다. SDWT 그룹을 연결하면 `groups`는 전체 경로의 문자열 배열입니다.
Portal DB 필드 이름과 Keycloak claim 이름은 별개의 계약입니다.

일반 신원 claim 전체를 공유하는 공통 Client Scope는 구현돼 있지 않습니다.
`sdwt-access-v1`은 그룹 발급용 scope이며 일반 신원 claim mapper를 대신하지 않습니다.
Headlamp는 별도 client의 그룹 mapper와 Kubernetes 권한 계약을 사용합니다.
