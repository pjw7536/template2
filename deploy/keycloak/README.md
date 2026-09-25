# 00. Keycloak 최초 설치 안내

Keycloak을 처음 설치하는 기준으로 설명합니다. **Keycloak 자체 설정과 사내 로그인 확인을 모두 마친 뒤 Portal·Headlamp를 연결합니다.**
대상은 Kubernetes namespace `etch-sso`, realm `etch`, 사내 Identity Provider alias `oidc`입니다.

## 설치 순서

| 순서 | 할 일 | 실행 안내 |
| --- | --- | --- |
| 1 | 환경변수·인증서·Worker 준비, 서버 설치 | [01 서버 설치](01_SERVER_SETUP.md) |
| 2 | Realm·사내 IdP·User Profile·수신 mapper 설정 | [04 Keycloak 설정](04_SETUP_FLOW.md) |
| 3 | 필요한 SDWT 그룹·사용자 초기 등록 | [07 SDWT 설정](07_SDWT_SETUP.md), 사용하는 경우 수행 |
| 4 | Keycloak Account Console에서 사내 로그인·사용자 정보 확인 | [Keycloak 설정 완료 확인](04_SETUP_FLOW.md#설정-완료-확인) |
| 5 | Portal·Headlamp 등 사용할 앱을 각각 연결 | [09 앱 연결](09_APP_CONNECTIONS.md) |

명령은 각 실행 안내에만 둡니다. 같은 설정을 다른 문서에서 반복 실행할 필요가 없습니다.
Keycloak 준비에는 Portal·Headlamp의 client ID·secret이 필요하지 않습니다.
문서 번호는 파일 식별용이며 위 표가 실제 진행 순서입니다. 실행 파일의 숫자는 설치 순서와 별개입니다.

등록용 CSV 양식은 [inputs](inputs/README.md)에 있습니다. 실제 값으로 작성한 파일을 초기 등록 도구에 전달합니다.

## 필요할 때 읽는 참고 문서

| 문서 | 설명하는 내용 |
| --- | --- |
| [02 환경변수](env/02_ENVIRONMENT.md) | 입력 파일과 값의 의미 |
| [03 TLS](03_TLS.md) | 사이트 인증서와 접속 주체별 CA 신뢰 준비 |
| [05 Discovery](05_DISCOVERY_SETUP.md) | 사내 접속 URL을 자동으로 가져오는 방식 |
| [06 사용자 필드](06_CLAIMS.md) | 사내 claim → 내부 저장 → 앱 claim 매핑 |
| [08 Kubernetes 원본](k8s/08_KUBERNETES.md) | manifest·설정 Job·생성 YAML의 역할 |

## 용어

| 용어 | 역할 |
| --- | --- |
| Realm | 사용자·앱·로그인 설정의 독립 영역 |
| Identity Provider / IdP | 사내 AD FS에 로그인을 위임하는 연결 |
| User Profile | 사용자 필드와 조회·편집 권한 |
| IdP mapper | 사내 claim을 Keycloak 사용자 필드에 저장 |
| Client / token mapper | 앱을 등록하고 사용자 정보를 앱 토큰으로 전달 |
| SDWT 그룹 | 소속과 구분되는 업무 접근 등급 |

설치 이후의 Git 반영·파일 관리와 과거 기록은 [Keycloak 운영 참고](operations/README.md)에 분리합니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
