# 권한관리(IAM) 배포

[권한관리 웹](../../apps/iam/README.md)이 사용하는 Keycloak 설정을 준비합니다. Kubernetes 배포 정의는 아직 없습니다(전환 미완료).

## Keycloak 준비

`scripts/setup_keycloak.py`는 대상 realm에 다음을 멱등 준비합니다. 기본은 조회만 하는 dry-run입니다.

| 대상 | 내용 |
| --- | --- |
| client `iam` | public client, 표준 흐름 + PKCE S256, redirect `<IAM_PUBLIC_URL>/*`, web origin은 IAM 주소 |
| client scope | `fullScopeAllowed=false`, realm-management `view-users`·`query-users`·`query-groups`·`manage-users`만 허용 |
| 그룹 `/iam/platform-admins` | 위 4개 관리 role. 가입한 사용자만 권한관리 웹을 사용 |
| realm 관리 이벤트 | 기록과 상세 기록을 켬 |

**준비물:** realm·User Profile 설정 완료, Keycloak 관리자 계정, 권한관리 웹 공개 주소.
**실행 위치:** 저장소 루트의 Bash.

```bash
read -r -p 'Keycloak 관리 접속 URL: ' KEYCLOAK_ADMIN_URL
read -r -p '관리자 계정: ' KEYCLOAK_ADMIN_USERNAME
read -r -s -p '관리자 비밀번호: ' KEYCLOAK_ADMIN_PASSWORD; echo
read -r -p '권한관리 웹 공개 URL: ' IAM_PUBLIC_URL
export KEYCLOAK_ADMIN_URL KEYCLOAK_ADMIN_USERNAME KEYCLOAK_ADMIN_PASSWORD IAM_PUBLIC_URL
make iam-keycloak-setup                       # dry-run, 계획만 출력
make iam-keycloak-setup IAM_KEYCLOAK_APPLY=1  # 적용
```

realm은 `KEYCLOAK_TARGET_REALM`(기본 `etch`)으로 바꿉니다. Keycloak 인증서를 OS가 신뢰하지 않으면 `KEYCLOAK_CA_FILE`로 CA를 지정합니다.
개발 Keycloak에는 `KEYCLOAK_ADMIN_URL=http://localhost:8180`, `KEYCLOAK_TARGET_REALM=portal`, `IAM_PUBLIC_URL=http://localhost:5174`로 실행합니다.

**기대 결과:** 계획 줄과 `적용 완료`가 출력되고, 다시 실행하면 client 갱신·role 연결만 계획에 남습니다.
**다음 단계:** [앱 역할 반영](../keycloak/docs/02-configure.md#앱-역할)(`make keycloak-access-apply`)으로 매트릭스 앱 목록을 저장하고,
Admin Console의 `Groups → iam → platform-admins → Members`에 관리자를 추가한 뒤 권한관리 웹에 로그인합니다.
**실패 확인:** 기존 `iam` client가 confidential이면 중단합니다. HTTP 상태가 출력되면 관리자 계정·URL·realm을 확인합니다.
