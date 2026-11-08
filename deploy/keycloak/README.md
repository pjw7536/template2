# Keycloak 배포 안내

[전체 배포 안내](../README.md) · [공통 준비·운영](../shared/docs/README.md)

사내 로그인을 앱에 연결하는 인증 서버입니다. namespace `etch-sso`, realm `etch`, 사내 Identity Provider alias `oidc`를 사용합니다.
먼저 Keycloak 자체의 사내 로그인을 확인한 뒤 Portal·Headlamp·Airflow를 연결합니다.

## 최초 설치 순서

파일 번호는 권장 읽기 순서입니다. 실행 명령은 각 문서의 단계와 완료 기준을 따릅니다.

| 순서 | 작업 | 완료 기준 |
| --- | --- | --- |
| 1 | [서버 준비](docs/01-setup.md) | 도구·Worker 디스크·기존 데이터 보존 조건 확인 |
| 2 | [환경설정](docs/02-environment.md) | 서버 기동용 실제 env·관리자·DB 입력 준비 |
| 3 | [TLS 준비](docs/03-tls.md) | 도메인 인증서·공용 TLS 준비 |
| 4 | [서버 배포](docs/04-deploy.md) | DB·Keycloak·Traefik 기동과 realm discovery 응답 확인 |
| 5 | [Realm·사내 로그인 설정](docs/05-keycloak.md) | IdP·User Profile·수신 mapper 설정과 시험 로그인 확인 |
| 6 | [SDWT 그룹·사용자 등록](docs/06-sdwt.md), 사용하는 경우 | 입력 CSV와 그룹·사용자 등록 결과 확인 |
| 7 | [앱별 연결](docs/07-app-connections.md) | 각 앱의 client·권한·로그인 확인 |

Keycloak 자체 준비에는 Portal·Headlamp의 client ID·secret이 필요하지 않습니다.
등록용 CSV 양식은 [inputs](inputs/README.md)에 있으며 실제 값으로 작성한 파일을 등록 도구에 전달합니다.
실행 명령은 각 절차에서 순서대로 수행합니다.

## 운영·참고

| 하려는 일 | 문서 |
| --- | --- |
| Git 갱신과 배포 파일 반영 | [운영 안내](docs/08-operations.md) |
| Discovery와 사내 OIDC 입력 확인 | [Discovery](docs/09-discovery.md) |
| 사내 claim·사용자 필드·앱 토큰 확인 | [claim 계약](docs/10-claims.md) |
| manifest·Job·생성 YAML 역할 확인 | [Kubernetes 원본](docs/11-kubernetes.md) |

## 용어

| 용어 | 역할 |
| --- | --- |
| Realm | 사용자·앱·로그인 설정의 독립 영역 |
| Identity Provider / IdP | 사내 AD FS에 로그인을 위임하는 연결 |
| User Profile | 사용자 필드와 조회·편집 권한 |
| IdP mapper | 사내 claim을 Keycloak 사용자 필드에 저장 |
| Client / token mapper | 앱을 등록하고 사용자 정보를 앱 토큰으로 전달 |
| SDWT 그룹 | 소속과 구분되는 업무 접근 등급 |

설치 이후의 Git 반영·파일 관리는 [Keycloak 운영 참고](docs/08-operations.md)에 분리합니다.

[전체 배포 안내](../README.md) · [Kubernetes 입문](../shared/docs/kubernetes/README.md)
