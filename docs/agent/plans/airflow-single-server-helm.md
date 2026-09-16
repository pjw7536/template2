# ExecPlan: Airflow 단일 서버 Helm 배포

## 목표
- deploy/airflow 아래 공식 Helm chart, 같은 노드 PostgreSQL, DB·로그 영구 저장 및 실행 절차를 제공한다.

## 현재 상태
- Airflow 2.11.0/LocalExecutor와 사내 패키지 Dockerfile, Portal 호출 DAG가 있다.
- 사내 Kubernetes만 허용하지만 Airflow 서버 검사는 미구현으로 실패한다.

## 범위
- deploy/airflow 배포 자산과 필요한 서버 검사·회귀 테스트·안내 연결을 수정한다.
- DAG·API 계약, 로컬 Compose, 기존 데이터와 실제 클러스터는 변경하지 않는다.

## 설계
- 공식 차트 버전과 checksum을 고정하고 오프라인 chart 파일을 지원한다.
- PostgreSQL은 Helm release 밖 StatefulSet으로 분리하고 두 local PV는 Retain 및 노드 affinity를 사용한다.
- LocalExecutor를 유지하고 기존 DAG를 사내 의존성 이미지에 추가한다.
- 실제 환경값·Secret은 무시되는 파일에서 읽고 실행하지 않는다. 예시값은 배포 차단한다.
- 새 설치는 DAG를 일시정지로 시작한다. 기존 DB 이전은 별도 수동 절차로 안내한다.

## 실행 단계
- [x] 차트·기존 계약 확인
- [x] 설정·렌더·배포·이미지 준비 구현
- [x] 서버 검사·문서 연결
- [x] 렌더 및 오류·민감값·오프라인 회귀 검증

## 검증
- 실제 공식 chart helm lint/template, 생성된 PostgreSQL·스토리지 구조 검사
- 배포 스크립트 단위·실패 경로 테스트 및 기존 scripts/tests
- 문서 감사, shell/Python 문법, git diff --check

## 위험과 대응
- 서버별 노드·경로·이미지 주소는 필수 설정으로 받고 예시값 배포를 금지한다.
- 동일 서버 장애는 HA로 복구되지 않는다. DB 백업과 복원 절차를 제공한다.
- DB 초기 비밀번호 변경 및 Helm DB migration은 자동 rollback 대상이 아님을 명시한다.
- 기존 Airflow 버전을 유지하는 전환이며 메이저 업그레이드는 별도 검증한다.

## 진행 기록
- 2026-09-14: 사용자 승인 구성에 맞춰 구현 시작. 클러스터 변경은 실행하지 않는다.

- 공식 chart 1.22.0 다운로드·SHA-256 검증, Helm 3.19.0 lint/template, 실제/예시 설정 검사 통과.
- 배포 회귀 14개, scripts/tests 전체 43개(배포 회귀 실행 wrapper 포함), agent 테스트 12개 통과.
- local 없는 Airflow 선택 checkout에서 실제 Helm 원본 검사 통과. 준비 도구가 없으면 명시적으로 실패함을 검사.
- 두 단계 이미지 빌드 성공. 외부 통신이 없는 일회성 Docker network의 PostgreSQL 16 + Airflow 2.11.0에서 DB migration, 관리자 생성·재실행·비밀번호 확인, DAG 8개 import, 차트 airflow.cfg 기반 /airflow/health 및 Basic Auth REST 응답 확인.
- 초기 컨테이너 검증은 DAG 파일 9개를 DAG 9개로 잘못 센 검증 assertion에서 실패했다. failure_alerts.py는 공통 helper이므로 실제 DAG 8개로 수정 후 전체 컨테이너 검증 통과. 제품 코드 결함은 없었다.
- 문서 감사·기존 Compose config·Python/shell/JSON 문법·git diff --check 통과.
- 실제 Kubernetes apply/Helm install, 사내 이미지 pull·스토리지 권한·Portal 네트워크 연결은 이 환경에서 실행하지 않았다. 서버 입력 후 배포 단계에서 확인한다.
