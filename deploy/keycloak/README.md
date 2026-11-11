# Keycloak 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

namespace `etch-sso`, realm `etch`, 사내 IdP alias `oidc`를 사용하는 인증 서버입니다.
Portal·Headlamp·Airflow는 각자 전용 client로 이 realm에 연결합니다.

## 의존 서비스

| 대상 | 필요한 내용 |
| --- | --- |
| Worker | 원본에 지정한 worker의 local PV 경로와 80/443 포트 |
| 공용 Traefik | `deploy/shared/ingress`. Keycloak 배포가 함께 적용 |
| TLS | 공용 `etch-sso/traefik-tls`에 Keycloak 도메인 인증서 등록 |
| DNS·VIP | 공개 도메인이 APP VIP로 연결됨 |
| 사내 AD FS | 사내 client ID·secret과 Keycloak broker redirect URI 등록 |

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [서버·env·TLS 준비](docs/01-prepare.md) |
| 2 | [DB·Keycloak 배포와 기동 확인](docs/02-deploy.md) |
| 3 | [Realm·사내 로그인·SDWT·앱 연결과 claim 계약](docs/03-configure.md) |

최초 설치에는 Portal client secret이 필요하지 않습니다.

## 완료 기준

Account Console(`<공개 Keycloak URL>/realms/etch/account/`)에서 사내 로그인이 성공하고,
Admin Console의 시험 사용자에 EPID username과 사내 claim 값이 저장되면 Keycloak 준비가 끝납니다.
이후 [앱 연결](docs/03-configure.md#앱-연결)을 진행합니다.

## 운영 링크

[원본 위치·설정 반영·공개 주소 변경·전달 YAML·claim 속성 이전](docs/04-operations.md)
