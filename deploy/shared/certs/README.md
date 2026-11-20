# 인증서 파일 보관 위치

도메인별 인증서·개인키와 공용 CA 원본을 보관하는 위치입니다.
파일을 받는 방법은 [인증서 발급](../docs/infrastructure/access.md#인증서-발급), 준비·추출 절차는 [인증서 원본 준비](../docs/certificates/prepare.md), 등록은 [공용 TLS 등록](../../README.md#공용-tls-등록), 등록 뒤 확인·갱신은 [인증서 적용](../docs/certificates/apply.md)에 있습니다.

| 위치·파일 | 역할 |
| --- | --- |
| `<도메인>/` | 사이트별 PFX·P7B 원본과 추출한 `fullchain.crt`, `private.key`. `make ops-deploy`의 준비 검사가 공개 host를 SAN에 가진 쌍을 여기서 찾아 공용 Traefik에 등록 |
| `<도메인>/backups/` | 추출 시 기존 `fullchain.crt`·`private.key` 보관 |
| `<도메인>/keycloak-ca-bundle.pem` | `make ca-bundle`이 `ca/`의 파일로 만드는 사내 CA 묶음([사내 CA 묶음](../../README.md#사내-ca-묶음)) |
| `ca/` | 사내 루트·중간 CA 원본 |
| `.gitignore`, `.gitkeep` | 실제 인증서·개인키의 Git 제외와 폴더 유지 |

실제 인증서·개인키는 Git에 넣지 않으며 서버마다 별도로 배치합니다. 파일을 배치해도 서버 설정은 자동 변경되지 않으며, 등록은 위 명령을 실행할 때 이뤄집니다.
