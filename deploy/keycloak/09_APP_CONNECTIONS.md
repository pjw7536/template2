# 09. Keycloak 준비 후 앱 연결

[전체 설치 순서](README.md) · 선행 조건: [Keycloak 설정 완료 확인](04_SETUP_FLOW.md#설정-완료-확인)

Keycloak Account Console의 사내 로그인과 사용자 정보 확인까지 완료한 뒤 진행합니다.
앱마다 별도의 client ID·secret·callback·토큰·권한을 설정합니다. 사내 AD FS client와 앱 client는 서로 다릅니다.
Portal과 Headlamp는 서로의 설치를 요구하지 않으므로 사용할 앱부터 연결합니다.

## Portal

[Portal client 등록 안내](../portal/k8s/jobs/keycloak-client/README.md)에서 입력 파일 작성 → client 등록 → Portal API 설정을 진행합니다.
이 작업은 `scripts/04-setup-portal-client.sh`를 사용하지만 파일명 숫자가 전체 설치 순서를 뜻하지는 않습니다.
Portal client와 사내 claim 16개·소속 claim 2개의 token mapper를 등록합니다.
Portal API 배포는 [Portal 배포 안내](../portal/README.md)를 따릅니다.

### SDWT 그룹을 Portal에 전달하는 경우

[07 SDWT 설정](07_SDWT_SETUP.md)에서 준비한 CSV 경로와 관리자 인증 환경변수를 사용합니다.
Portal client 등록 후 아래를 실행합니다. `portal`은 실제 Portal client ID로 맞춥니다.
사용자를 다시 등록하지 않으므로 사용자 CSV는 전달하지 않습니다.

```bash
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=0 KEYCLOAK_SDWT_VALIDATE_ONLY=0
make keycloak-sdwt-init KEYCLOAK_SDWTS_CSV="$KEYCLOAK_SDWTS_CSV" KEYCLOAK_USERS_CSV= KEYCLOAK_SDWT_CLIENTS=portal KEYCLOAK_SDWT_APPLY=1 KEYCLOAK_SDWT_VALIDATE_ONLY=0
```

`sdwt-access-v1` 기본 scope를 연결하고 `groups`를 전체 경로 배열로 발급합니다.
선택 client의 Access Token 수명을 300초로 설정합니다. 이 설정만으로 앱의 권한 판정 코드가 구현되지는 않습니다.
앱이 실제 자원의 SDWT와 그룹 등급을 검사하는지 확인해야 합니다.

## Headlamp

[Headlamp 최초 설치 안내](../headlamp/README.md)의 준비 → TLS·CA → 전용 client·Secret → API server → 배포·검증 순서로 진행합니다.
Keycloak의 Headlamp client 등록만으로는 Kubernetes에 접근할 수 없습니다.
API server의 OIDC 신뢰 설정과 RBAC까지 완료해야 합니다.

Headlamp의 `headlamp-admins`는 클러스터 전체 관리 권한을 위한 전용 그룹입니다.
SDWT 업무 그룹이나 Portal용 권한을 대신 연결하지 않습니다.
Headlamp에는 Portal 전용 등록 명령을 사용하지 않습니다.

## 앱별 완료 기준

| 앱 | 확인할 결과 |
| --- | --- |
| Portal | 사내 로그인·callback 성공, 새 토큰의 신원 claim, 필요한 소속·그룹과 앱의 접근 판정 |
| Headlamp | 브라우저 로그인 성공, 허용한 관리자의 접근 성공, 허용하지 않은 사용자의 접근 거부 |
| 추가 OIDC 앱 | 전용 client·redirect URI·issuer/JWKS·필요한 claim·권한 판정 확인 |

새 client를 만드는 것만으로 Portal의 mapper가 다른 앱에 복제되지는 않습니다.
claim 이름·대소문자·자료형·발급 위치와 실제 값을 앱에서 확인합니다.
