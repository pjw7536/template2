# ExecPlan: 앱별 Kubernetes 배포 진입점

## 목표
- Keycloak부터 앱별 검사·배포를 한 단계씩 실행한다.

## 현재 상태
- server-up은 Keycloak 재적용과 Airflow 배포가 결합되어 있다.
- Keycloak env/certs 입력 폴더가 준비되어 있다.

## 범위
- Keycloak·Airflow 앱별 스크립트와 Make 명령, 운영 안내와 회귀 검사.
- 기존 server-up 호환 유지. Portal·Monitoring의 새 배포 구현은 제외.

## 설계
- Keycloak은 Airflow 모듈·차트 없이 env/TLS 최초 Secret 등록 후 원본을 적용한다.
- 기존 Secret과 다른 입력은 중단하며 별도 갱신 절차를 안내한다.
- Keycloak 재배포는 Traefik namespace/VIP 배치를 보존한다.
- Airflow는 자신의 리소스와 필요한 공용 ingress 연결만 적용한다.
- context 필수, check-only 조회 전용, DB 삭제·초기화 코드 없음.

## 실행 단계
- [x] 앱별 스크립트·Make 명령 구현
- [x] 신규·기존 Secret 및 앱 배포 격리 회귀 검사
- [x] 문서와 기존 검사 확인

## 검증
- Python 배포 단위 검사와 Node 배포 회귀 검사
- make server-check APP=keycloak-airflow
- make -n 및 각 CLI --help

## 위험과 대응
- 공유 ingress 회귀: 기존 namespace·VIP 보존 함수를 재사용한다.
- credential 변경으로 DB 접속 실패: 기존 Secret 불일치 시 적용 전에 중단한다.
- 서버 연결 정보 없음: 실제 배포는 하지 않고 코드·렌더·테스트 범위를 명시한다.

## 진행 기록
- 2026-09-15: 앱별 배포 설계 확정.
- 2026-09-15: keycloak-check/up, airflow-check/up 추가. 기존 server-up 호환 유지. 빈 DB 재설치 안내도 Keycloak 단독 순서로 변경.
- 2026-09-15: 공용 Python 테스트 30개 통과(실제 OpenSSL 검증·Airflow 없는 checkout CLI 포함). Node 배포 회귀 14개와 Keycloak/Airflow 원본·Helm 렌더 검사 통과. CLI 도움말·Make dry-run·문서 링크·재설치 명령 Bash 구문 통과. 빈 context는 실행 전에 예상대로 거부.
- 2026-09-15: 서버 context가 없어 실제 이미지 pull·worker 디스크·기동·로그인은 미검증. DB 삭제나 클러스터 적용은 수행하지 않음.
