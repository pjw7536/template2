# 인증서 파일 보관 위치

도메인별 인증서·개인키와 공용 CA 원본을 보관하는 위치입니다.
준비·추출·등록·갱신 절차는 [인증서 원본 준비](../docs/certificates/prepare.md)에서 시작합니다.

| 위치·파일 | 역할 |
| --- | --- |
| `<도메인>/` | 사이트별 PFX·P7B 원본과 추출한 `fullchain.crt`, `private.key` |
| `<도메인>/backups/` | 추출 시 기존 `fullchain.crt`·`private.key` 보관 |
| `ca/` | 사내 루트·중간 CA 원본 |
| `.gitignore`, `.gitkeep` | 실제 인증서·개인키의 Git 제외와 폴더 유지 |

실제 인증서·개인키는 Git에 넣지 않으며 서버마다 별도로 배치합니다. 파일을 배치해도 서버 설정은 자동 변경되지 않습니다.
