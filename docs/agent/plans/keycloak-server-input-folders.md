# ExecPlan: Keycloak 서버 입력 폴더

## 목표
- 프로젝트 복사 후 정해진 폴더에 env와 인증서를 넣어 사용할 수 있게 한다.

## 현재 상태
- env/prod.env.example과 기본 env 경로가 존재한다.
- 인증서 문서는 기존 서버 외부 경로를 사용한다.

## 범위
- Keycloak 입력 폴더·Git 제외 규칙·사용 안내만 추가한다.
- DB 초기화와 클러스터 배포는 수행하지 않는다.

## 설계
- 기존 env/prod.env 계약을 유지하고 certs/를 선택적인 프로젝트 내부 입력 위치로 제공한다.
- 실제 입력은 Git에서 제외하며 기존 파일을 덮어쓰지 않는다.

## 실행 단계
- [x] 폴더와 안내, Git 제외 규칙 작성
- [x] 기존 prod.env 존재와 0600 권한 확인, 기존 파일 유지
- [x] 경로·Git 제외·Keycloak 원본 검사

## 검증
- git check-ignore로 실제 파일과 문서의 제외 여부 확인
- 문서 상대 링크 검사와 make server-check APP=keycloak

## 위험과 대응
- 비밀 파일 유입: env와 certs는 예시·문서 외 파일을 모두 제외한다.
- 기존 입력 손실: 파일 존재 시 복사하지 않는다.

## 진행 기록
- 2026-09-15: 입력 폴더 준비 시작.
- 2026-09-15: env/certs 안내와 로컬 Git 제외 규칙 추가. 문서 링크·Bash 구문·Git 제외 검사 및 make server-check APP=keycloak 통과. 실제 인증서 등록·클러스터 배포는 수행하지 않음.
