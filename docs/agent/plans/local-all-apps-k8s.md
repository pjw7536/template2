# ExecPlan: 로컬 전체 앱 Kubernetes 전환

## 목표
- 한 PC의 kind에서 Portal·Keycloak·Airflow·FTP·MinIO·mock·모니터링을 실행한다.
- 새 Docker PostgreSQL을 사용하고 기존 DB·데이터는 보존한다.
- make dev를 전체 실행으로 전환하고 대표 통합 시나리오를 검증한다.

## 현재 상태
- 로컬 Kubernetes는 Portal 중심이며 Airflow·모니터링의 공통 Helm 배포 도구가 있다.
- kind·Helm과 고정 chart가 준비되어 있다. 기존 PostgreSQL만 실행 중이다.
- 로컬 manifest 렌더, Airflow 19개·모니터링 8개 테스트가 통과했다.

## 범위
- local의 실행·설정·영속화, 공통 배포 도구의 외부 DB·values 확장, Makefile·검사·문서.
- 실제 사내 연동, 전체 업무 기능 전수 검증, 기존 DB 데이터 이전은 제외한다.

## 설계
- 공통 정의는 deploy에서 재사용하고 local이 전용 overlay를 소유한다.
- PostgreSQL의 dashboard·airflow·keycloak DB와 계정을 분리한다.
- Service/EndpointSlice를 통해 kind 밖 DB를 연결하고 재실행 시 주소를 갱신한다.
- 호스트 디스크를 kind worker에 연결해 클러스터 재생성에도 파일을 보존한다.
- 인증은 Keycloak, 업무 외부계는 adfs_dummy를 사용한다.
- make dev/down은 Kubernetes, compose-dev/compose-down은 이전 Compose 진입점이다.

## 실행 단계
- [x] 공통 실행 도구·DB·영속 저장소 구성
- [x] Portal·Keycloak·mock·FTP 연결
- [x] Airflow 외부 DB와 모니터링 연결
- [x] Makefile·문서·회귀 테스트 갱신
- [x] 실제 전체 기동·통합·재기동·보존 검증

## 검증
- Kustomize·Helm 렌더, 배포 도구 단위 테스트, tooling 테스트, 서버 선택 checkout 검사.
- 로그인·RAG/챗·메일/MinIO·Airflow→API·FTP 업로드/파일 처리·모니터링 수집.
- 반복 배포와 DB 주소 갱신, Pod·클러스터 재생성 후 데이터 보존.
- 전체 앱을 30분 관찰해 OOM·반복 재시작·지속 수집 실패 여부를 확인한다.

## 위험과 대응
- 로컬 메모리 약 16GB: Airflow 동시성·Prometheus 보존을 로컬 values로 제한한다.
- FTP passive NAT: worker 포트 매핑과 localhost 광고 주소를 함께 설정한다.
- 기존 데이터·Secret: 일반 기동과 종료에서 초기화·volume 삭제를 수행하지 않는다.

## 진행 기록
- 2026-09-16: 사용자 계획 승인, 구현 시작. 기존 작업 트리 변경 없음.
- 2026-09-16: 전체 실행 도구·외부 DB·호스트 영속화·Makefile 전환 구현. tooling 61개, 로컬 구성 6개, 기존 Airflow 19개·Monitoring 8개 테스트 통과.
- 2026-09-16: Django check·makemigrations --check 통과, server-check APP=all·env·Compose 검사 통과.
- 2026-09-16: 현재 PC의 기존 포트 점유로 FTP 16380·passive 18076–18079를 Git 제외 local env에 적용.
- 2026-09-16: MinIO 공개 pull 거부를 확인해 Docker 캐시 반입과 이미지 override 지원. 다중 플랫폼 archive는 현재 플랫폼으로 containerd에 반입.
- 2026-09-16: 실제 로그인·Portal 사용자·챗 스트리밍·RAG·메일·MinIO 저장/다운로드 통과. 전체 기동과 파일/배치/모니터링 검증 진행 중.
- 2026-09-16: make k8s-smoke 전체 통과, Chromium 실제 로그인·화면 렌더·pageerror 없음 확인.
- 2026-09-16: 전체 Django 1142개 테스트 중 개발 env에 의존한 인증 2개 실패를 확인. 테스트 명령에 기존 표준 test env를 사용하도록 분리하고 재검증한다.
- 2026-09-16: 구조 감사는 작업 전부터 존재한 무시된 apps/web·루트 airflow 디렉터리 때문에 실패했다. 별도 서버 Headlamp 작업 파일도 나타났으며 이 작업에서 수정·삭제하지 않는다.
- 2026-09-16: 표준 test env로 Django 1142개 전체 재검증 통과. 공통 Airflow 20개·Monitoring 8개, 로컬 구성 7개, tooling 63개 통과.
- 2026-09-16: make down → make dev로 클러스터와 외부 DB 컨테이너를 재생성했다. Portal 적재 행·Keycloak 사용자·Airflow 성공 이력, MinIO 객체·Grafana dashboard 보존 검증 통과.
- 2026-09-16: 재생성 후 강화한 통합 검사 통과. Airflow DAG import 오류 0건, 실제 Outbox 작업의 DAG → Portal API → RAG 처리 확인. 같은 클러스터에 make dev 반복 적용도 통과.
- 2026-09-16: server-check APP=all·문서 감사 통과. 배포 완료 상태에서 30분 안정성 관찰을 시작했다.
- 2026-09-16: 1801초 동안 41회 검사 완료. 실행 Pod 30개·Prometheus 대상 18개가 모든 표본에서 정상이며 재시작·OOM·수집 실패 0건. 앱은 실행 상태로 유지했다.

## 최종 검증 결과

| 검사 | 결과 |
| --- | --- |
| `make dev`, `make down` 후 재기동, 같은 클러스터 반복 배포 | 통과 |
| `make k8s-smoke`와 Chromium 로그인·화면 렌더 | 통과 |
| PostgreSQL 3개 DB·MinIO 객체·Grafana dashboard 보존 | 통과 |
| `make check-api makemigrations-check test-api` | 통과, Django 테스트 1142개 |
| Airflow·Monitoring·로컬 구성 단위 테스트 | 20개·8개·7개 통과 |
| tooling 회귀 검사 | 63개 통과 |
| 서버 전체 원본·env profile·Compose·문서 검사 | 통과 |
| 30분 안정성 관찰 | 41개 표본 통과, 재시작·OOM 0건 |
| 저장소 전체 폴더 구조 감사 | 기존 무시된 `apps/web`·루트 `airflow` 잔여 폴더 때문에 실패, 이 작업 범위에서 삭제하지 않음 |

관찰·통합 검사 로그는 Git 제외 `local/shared/runtime/stability-check.log`와 `smoke-check.log`에 보관한다.
사내 실제 외부계 연결·전체 업무 기능 전수 검증·부하 시험은 수행하지 않았다.
