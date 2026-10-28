# ExecPlan: 추가 배포 리뷰 후속 수정

## 목표
- MinIO 미배포 상태에 맞춰 최초 설치와 초기화 재시도 절차를 구분한다.
- Airflow 필수 리소스 누락을 공용 라우팅 변경 전에 차단한다.
- Helm override를 포함한 최종 Pod toleration으로 노드 taint를 검사한다.

## 현재 상태
- 운영 MinIO는 아직 설치하지 않았다. 현재 manifest를 최초 생성할 때 Job 불변 필드 문제는 발생하지 않는다.
- 필수 Secret·ConfigMap·IngressClass 조회가 실제 Airflow deploy에만 있어 check 명령과 공용 리소스 변경 전에 누락을 발견하지 못한다.
- taint 검사는 기본 허용 목록을 고정해서 외부 DB와 Helm toleration override 조합을 잘못 거부한다.
- 이전 작업과 사용자 MinIO·Ingress 미커밋 변경을 보존한다.

## 범위
- deploy/airflow/scripts, deploy/shared/scripts 및 관련 회귀 테스트.
- deploy/portal의 최초 설치·초기화 재시도 안내와 Airflow 운영 문서.
- 실제 클러스터 적용·기존 Job 삭제·업무 앱 소스 변경은 수행하지 않는다.

## 설계
- 사전 검사와 배포가 같은 필수 리소스 검사를 사용한다. 최초 TLS 복사는 검증된 생성 예정 Secret만 예외로 둔다.
- Helm 최종 렌더를 kubectl의 읽기 전용 client dry-run으로 JSON 변환하고 표준 라이브러리로 Pod toleration을 읽는다.
- 내부 PostgreSQL의 별도 Pod 설정도 검사해 Airflow override가 DB의 배치 불가를 숨기지 않게 한다.
- MinIO 최초 설치는 삭제 없이 진행한다. 초기화 재실행이 필요한 경우 완료·실패 상태와 원인을 확인하고 해당 Job만 재생성하는 절차를 문서화한다.
- env·DB·공개 API 계약은 유지한다.

## 실행 단계
- [x] 실패 조건과 TLS 최초 복사·정상 override 회귀 테스트 추가
- [x] 공통 사전 검사와 최종 toleration 검사 연결
- [x] 최초 설치·재시도·운영 검사 문서 동기화
- [x] 관련 회귀·서버 경계·렌더·문서 검사

## 검증
- Airflow·공통 배포 Python 단위 테스트와 실제 Helm override 렌더 검사.
- `PATH="$PWD/.tools/bin:$PATH" make tooling-test`의 source 없는 서버 checkout 검사 포함.
- `make k8s-render-local`, `PATH="$PWD/.tools/bin:$PATH" make server-check APP=all`.
- `make audit-docs`, `git diff --check`.

## 위험과 대응
- TLS Secret을 복사하기 전에 전체 검사를 실행하므로 생성 예정 TLS만 좁게 허용하고 나머지 누락은 차단한다.
- NoSchedule·NoExecute의 effect, Exists·Equal·value와 명시적인 한시 toleration을 검증한다.
- MinIO 최초 설치에서 불필요한 기존 리소스 삭제를 실행하지 않는다. 재시도 안내도 PVC와 데이터는 보존한다.

## 진행 기록
- 2026-10-27: 사용자 설명에 따라 운영 MinIO 미설치 전제로 후속 수정 범위를 확정했다.
- 2026-10-27: 필수 Secret·ConfigMap·IngressClass 누락을 check와 deploy 모두 공용 변경 전에 차단했다. 검증된 최초 TLS 복사만 생성 예정 리소스로 허용했다.
- 2026-10-27: 최종 Helm Pod의 toleration·nodeSelector와 내부 DB를 각각 검사하도록 연결했다. 실제 Helm 렌더와 kubectl client dry-run에서 외부 DB의 override Pod 5개는 통과하고 같은 조건의 내부 DB는 차단했다.
- 2026-10-27: Airflow Python 40개, 공통 배포 Python 52개, tooling 77개 테스트가 통과했다. tooling의 앱 소스·local 없는 서버 checkout 검사도 통과했다.
- 2026-10-27: 로컬 진입점 7개 렌더링, 6개 앱 서버 원본 검사, 문서 검사와 diff 공백 검사를 통과했다. MinIO 재시도 명령의 상태 판별 5가지를 모의 명령으로 확인했으며 실제 배포·삭제는 실행하지 않았다.
