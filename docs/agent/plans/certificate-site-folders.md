# ExecPlan: 사이트별 인증서 폴더

## 목표
- 서버 인증서를 도메인별로 구분하고 공용 CA는 별도로 보관한다.

## 현재 상태
- deploy/shared/certs에 README와 Git 제외 규칙만 있다. 실제 인증서는 없다.
- Headlamp OIDC 가이드가 공용 폴더 바로 아래 파일을 참조한다.

## 범위
- 인증서 폴더 구조·Git 제외 규칙·README·OIDC 가이드.
- 기존 배포 도구의 기본 경로와 서버 Secret은 변경하지 않는다.

## 설계
- etch-sso.samsungds.net: Keycloak 원본·fullchain·key·생성 CA 묶음.
- etch.samsungds.net: Headlamp 도메인 원본·fullchain·key.
- ca: 루트·중간 인증기관 원본.
- 폴더는 .gitkeep으로 유지하고 실제 파일은 계속 Git에서 제외한다.
- Keycloak은 기존 KEYCLOAK_CERTS 인자로 새 하위 경로를 지정한다.

## 실행 단계
- [x] 폴더 생성과 Git 제외 규칙 조정
- [x] 파일 배치·CA 생성·배포 참조 경로 정합성 수정
- [x] 제외 규칙·문서 명령·서버 경계 검사

## 검증
- git check-ignore로 실제 인증서 제외 및 안내·폴더 표식 추적 확인.
- 문서 Bash 문법·로컬 링크·CA 생성 명령의 새 경로 검증.
- node --test apps/tooling/tests/server-checkout.test.cjs
- git diff --check

## 위험과 대응
- 서버에 이미 넣은 파일은 자동 이동되지 않으므로 README에 새 배치 명시.
- CA 원본과 사이트별 산출물을 구분하고 기존 파일을 덮어쓰지 않는다.

## 진행 기록
- 2026-09-22: 사용자 요청에 따라 사이트별 디렉터리 구조 확정.

- 2026-09-22: 폴더·참조 경로 변경 완료. Git 제외·문서 링크·Bash 문법, 임시 인증서 PEM/DER 및 실패 시 보존 검사 통과. 서버 경계 검사 17개 통과. 실제 서버 파일 이동·배포는 수행하지 않음.
