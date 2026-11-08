# 인증서 파일 보관 위치

도메인별 인증서·개인키와 공용 CA 원본을 보관하는 위치입니다.
준비·추출·검증·등록·갱신 절차는 [인증서 관리](../docs/certificates/README.md)를 따릅니다.

| 위치·파일 | 역할 |
| --- | --- |
| `<도메인>/` | 사이트별 인증서 원본과 `fullchain.crt`, `private.key` |
| `ca/` | 사내 루트·중간 CA 원본 |
| `.gitignore`, `.gitkeep` | 실제 인증서·개인키의 Git 제외와 폴더 유지 |

실제 인증서·개인키는 Git에 넣지 않습니다. 파일을 배치해도 서버 설정은 자동 변경되지 않습니다.
공용 TLS 등록과 OIDC CA 신뢰 설정은 각각 [상세 절차](../docs/certificates/apply.md)에서 확인합니다.
