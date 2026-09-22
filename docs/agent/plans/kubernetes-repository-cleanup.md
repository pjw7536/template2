# ExecPlan: Kubernetes 기준 저장소 구조 정리

## 목표
- apps는 직접 개발 소스, deploy는 서버 배포 원본, local은 개발 환경 차이를 소유하도록 정리한다.
- 미사용 폴더를 제거하고 로컬 서비스 소유권·실행 도구·검사·문서를 일치시킨다.

## 현재 상태
- 서버는 Kubernetes 전용이며 로컬 DB·API 검사·CI용 Compose는 사용 중이다.
- 빈 apps/web 및 루트 airflow 때문에 구조 감사가 실패한다.
- 로컬 Keycloak·Headlamp·Traefik·mock 정의가 local/portal/k8s에 함께 있다.
- 기존 Kubernetes 가이드 9개와 kubernetes-guide-simplify 계획의 사용자 변경을 보존한다.

## 범위
- deploy/local 구조, apps/tooling, Makefile, 관련 문서·ignore 규칙.
- 앱 업무 로직·API·DB schema·인증 동작은 변경하지 않는다.
- DB·호스트 데이터·실제 env·인증서·runtime·chart 캐시·사용 중인 생성 YAML은 보존한다.

## 설계
- Keycloak은 local/keycloak/k8s, Headlamp는 local/headlamp, mock은 local/adfs_dummy/k8s로 이동한다.
- local/shared/k8s는 공통 namespace·Traefik·외부 PostgreSQL Service와 전체 Kustomize 집계를 소유한다.
- Portal은 API·Web·MinIO·migration·전용 스토리지를 유지한다.
- 기존 리소스 식별자·ConfigMap 내용과 해시·포트·마운트·기동 순서와 Make 명령을 유지한다.
- apps.json에 Keycloak·Headlamp 로컬 경로를 반영하며 서버 checkout은 local·소스 없이 동작한다.
- 보조 Compose는 유지한다. 데이터 이전이나 클러스터 재생성은 없다.

## 실행 단계
- [x] 변경 전 렌더·사용자 변경 보존 기준 확보 및 빈 잔재 제거 (기존 Airflow 자동 재시작 해제·중지 완료)
- [x] 앱별 로컬 소유권과 전체 집계 분리
- [x] 실행 도구·앱 목록·구조 및 서버 checkout 검사 갱신
- [x] 문서·ignore 규칙 정리
- [x] 렌더 동등성·회귀 검사 및 결과 기록

## 검증
- 변경 전후 Kustomize 출력의 리소스 식별자·내용 비교
- make audit / env-profile-key-check / compose-check / k8s-render
- PATH에 .tools/bin을 추가한 tooling 회귀 검사 및 make server-check APP=all
- 앱별 렌더·Keycloak/mock 선택 갱신·서버 checkout 독립성 회귀 검사
- 변경 문서 상대 링크·폐기 경로 참조·git diff --check
- 실제 서버 배포·데이터 생성 smoke 검사는 수행하지 않는다.

## 위험과 대응
- 사용자 변경 유실: 기존 파일의 해시를 비교하고 해당 가이드는 수정하지 않는다.
- 데이터 삭제: 명시한 빈 잔재에만 rmdir를 사용하고 파일이나 링크가 있으면 삭제하지 않는다.
- Kustomize 이동으로 해시·namespace 변경: 변경 전후 전체 리소스의 정규화 결과를 비교한다.
- 앱 외 검사 실패: 기존 실패 여부를 구분하고 업무 로직으로 수정 범위를 넓히지 않는다.

## 진행 기록
- 2026-09-22: Ubuntu Docker의 `/etc/docker/daemon.json`에 live-restore를 적용하고 `/etc/systemd/system/docker.service.d/20-native-socket.conf`에 `/run/docker-native.sock` 관리 연결을 추가했다. 데몬 재시작 전후 PostgreSQL·MySQL·FTP PID가 동일하며 Docker Desktop의 kind도 유지됨을 확인했다. 기존 Airflow scheduler·webserver만 restart=no·exited로 전환하고 빈 잔재 8개를 rmdir로 제거했다. 컨테이너·볼륨·데이터는 삭제하지 않았다. 호스트 설정은 Git 관리 대상이 아니다.
- 2026-09-22: 최종 구조·문서 감사, tooling 테스트 68개, Portal 로컬 env 키, Compose 검사 및 diff 공백 검사 통과. 앞선 검증에서 Python 38개, Headlamp 서버 원본 검사와 로컬 Kubernetes 렌더도 통과했다. 실제 사내 배포·OIDC 로그인은 미수행이며 현재 변경사항 전체를 main에 커밋·푸시한다.
- 2026-09-22: 사용자 요청으로 잔재 정리와 main 푸시를 재개한다. Docker Desktop과 Ubuntu Docker가 동시에 실행 중이며 기본 socket은 Desktop으로 연결된다. Ubuntu의 기존 Airflow scheduler·webserver는 restart=always와 이전 루트 airflow 마운트를 유지한다. Ubuntu Docker에 live-restore를 적용한 뒤 전용 관리 socket을 추가하여 두 컨테이너만 자동 재시작 해제·중지한다. 다른 컨테이너의 PID·DB·볼륨을 보존하고 빈 디렉터리는 rmdir로만 제거한 뒤 검증한다.
- 2026-09-17: 계획 확정. 환경 키·Compose·Kustomize 및 로컬 설정 테스트 7개 통과, 구조 감사는 빈 잔재 2개로 실패.
- 2026-09-17: 미사용 빈 디렉터리 31개 제거 작업 수행. root 소유 잔재는 네트워크 없는 임시 컨테이너의 rmdir로만 제거했다. 이후 루트 airflow와 하위 빈 디렉터리 4개가 재생성되어 이 5개 경로의 영구 정리는 미완료다. 실행 컨테이너·DB·volume은 변경하지 않았다.
- 2026-09-17: 배포 입력·접속 스크립트 8개를 소유 영역으로 이동하고 앱별 Kustomize·shared 집계를 구성했다. 변경 전후 35개 Kubernetes 리소스의 내용·식별자가 모두 동일하다.
- 2026-09-17: Keycloak/mock 선택 갱신은 각 앱 원본 전체를 적용하며 Secret 준비는 소유 서비스별로 구분한다. mock 이미지에는 새 k8s 디렉터리가 들어가지 않도록 .dockerignore를 추가했다.
- 2026-09-17: 앱 목록 기반 구조·서버 checkout 검사를 보강했다. 기존 Headlamp 회귀 검사가 HTTPS 예시를 포트 포워딩 전용으로 가정해 실패하여, 명시적 가짜 env로 두 접속 방식을 검증하도록 수정했다. 서버 배포 동작은 변경하지 않았다.
- 2026-09-17: make audit 통과(Python 테스트 27개 포함) 후 루트 airflow 재생성으로 최종 구조 감사에 다시 위반이 발생했다. 나머지 감사와 make tooling-test 68개, env-profile-key-check·compose-check·k8s-render·server-check APP=all은 통과했다(Helm은 .tools/bin 사용).
- 2026-09-17: 수정 안내 문서 상대 링크 54개 확인. 실제 env 6개 Git 제외·공개/검사 env 6개 유지 확인. 기존 Kubernetes 가이드 9개와 사용자 계획 1개의 SHA-256이 작업 전과 동일하다.
- 2026-09-17: 실제 클러스터 적용·DB 이전·통합 smoke·이미지 빌드는 수행하지 않았다. 자동 커밋·push 없이 작업 트리 변경으로 남긴다.
- 2026-09-17: 호스트에서 재시작되는 기존 tailwind-airflow-scheduler-1·tailwind-airflow-webserver-1의 컨테이너 설정에 루트 airflow/config·dags·plugins·logs 바인드 마운트가 남아 있음을 확인했다. 현재 Docker CLI 목록에는 두 컨테이너가 나타나지 않아 호스트 runtime 경계도 확인이 필요하다. 기존 계획은 실행 컨테이너 변경을 제외하므로 두 컨테이너 중지·자동 재시작 해제의 범위 확장을 사용자에게 질문했다.
