# ExecPlan: 배포 env 단일 파일 관리

## 목표
- 사용자 지시에 따라 비밀번호·토큰도 앱별 기존 env에 함께 저장하고 Git에 포함한다.
- 인증서·개인키 파일은 Git에서 제외한다.

## 현재 상태
- Airflow·Keycloak·Portal API·MinIO는 일반 env와 인접 secrets.env로 분리되어 있다.
- Bash 공통 로더, Keycloak·Airflow가 인접 파일을 자동 병합한다.

## 범위
- 배포 env, 로더, Airflow 초기화, 관련 테스트·운영 문서와 Git 제외 규칙.
- 실제 Kubernetes Secret·DB·실행 중인 서버는 변경하지 않는다.

## 설계
- 기존 병합 결과를 기본 env에 저장한 뒤 값 동일성을 검증하고 분리 파일을 제거한다.
- 인접 파일 자동 병합 코드를 제거하고 지정된 env만 읽는다.
- Airflow init-secrets는 기존 일반 설정을 보존하며 같은 env에 초기 키를 기록한다. 기존 키가 있으면 재생성을 거부한다.
- Kubernetes Secret 리소스 사용과 로그에 credential을 노출하지 않는 동작은 유지한다.

## 실행 단계
- [x] 기존 env 값 통합·동일성 검사
- [x] 로더·초기화·회귀 테스트 변경
- [x] 운영 문서 갱신
- [x] 관련 검사 실행

## 검증
- Python 배포 단위 검사, Bash 문법 검사, 환경·서버 체크아웃 Node 테스트.
- 앱별 server-check와 Git 포함·인증서 제외 검사.

## 위험과 대응
- 값 유실: 통합 전후 모든 키·값을 메모리에서 비교하고 값은 출력하지 않는다.
- 기존 서버의 분리 파일: 최신 통합 env를 사용하도록 안내하고 자동 병합 종료를 명시한다.

## 진행 기록
- 2026-09-25: 사용자가 private 저장소의 env에서 비밀값 전용 파일 분리를 없애도록 요청했다.
- 2026-09-25: env 4쌍의 통합 전후 키·값 동일성 검증 후 분리 파일 제거. Python 공통 37개·Airflow 22개, Node 환경·서버 체크아웃 53개 통과. Bash 문법, 문서 audit, Keycloak·Airflow·Portal server-check 및 Git 제외 검사 통과. 실제 서버 배포는 수행하지 않았다.

## 추가 범위: 배포 예시 env 제거
- 사용자 지시에 따라 deploy의 env.example 8개를 삭제하고 env 하나를 Git 원본으로 사용한다.
- 키 스키마는 코드에 유지하고 검사·초기화·문서·로컬 Airflow 참조를 변경한다. 로컬 전용 shared 예시는 이번 배포 범위 밖이다.
- [x] 파일·참조·독립 테스트 입력 전환
- [x] 환경·배포·로컬 설정 회귀 검사
- 2026-09-25: 배포 예시 env 8개 삭제, 키 계약은 코드에 보존. Airflow 22·Monitoring 8·Headlamp 12·공통 37·로컬 설정 9·Node 환경 36·서버 체크아웃 17개 통과(총 141개). 전체 앱 server-check, 문서 audit 통과. 로컬 전용 shared env 예시는 유지했다.
