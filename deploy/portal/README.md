# Portal 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

namespace `tailwind-internal`에 Portal API·Web·edge-nginx를 배포합니다. 공개 주소는 `https://etch.samsungds.net`입니다.

## 의존 서비스

| 대상 | 필요한 내용 |
| --- | --- |
| PostgreSQL | Portal 전용 외부 DB·계정과 `pg_trgm` extension. Keycloak DB와 별개 |
| Keycloak | [Keycloak 설치](../keycloak/README.md)의 사내 로그인 확인 완료 |
| MinIO | [공용 MinIO](../minio/README.md)의 접근 계정·bucket 권한 |
| 공용 Traefik·TLS | Portal 도메인 인증서와 감시 namespace 연결 |
| 이미지·저장소 | API·Web 고유 태그, 필요한 업무 파일 PVC |

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [환경설정·Keycloak client 등록·migration·배포·검증](docs/01-install.md) |
| 2 | [최초 운영자·앱 역할·데이터 권한](docs/02-access.md) |

## 완료 기준

API health, Keycloak login/callback/logout, MinIO 시험 파일 업로드·다운로드가 성공하고
최초 운영자가 새 로그인으로 앱·데이터 접근을 확인하면 설치가 끝납니다.

## 운영 링크

[env·Secret 반영·재시작·health 확인](docs/03-operations.md) · [DB schema 변경](docs/01-install.md#3-migration)
