# ExecPlan: 공용 MinIO 독립 배포

## 목표
- MinIO를 `deploy/minio`와 운영 `minio` namespace가 소유하는 공용 앱으로 분리한다.
- Portal과 다른 앱은 공용 Service를 사용하며 콘솔 `/minio-console/`와 파일 `/minio/` 주소를 유지한다.
- 사내 이미지 미러·노드·볼륨·공개 주소를 env로 지정하고 독립 검사·배포 명령을 제공한다.

## 현재 상태
- MinIO Deployment/PVC/Service/Job·콘솔 Ingress·운영 env가 Portal에 속해 있다.
- `/minio/` 파일 경로는 Portal Nginx에 의존한다.
- 운영 설치가 MinIO rollout에서 대기한다는 보고가 있다. MinIO·mc는 Docker Hub 직접 주소이며 운영 Pod 이벤트를 요청했다. 현재 작업 환경에는 local context만 있다.

## 범위
- MinIO 배포 앱·카탈로그·공통 명령·Portal 소비 연결·local 원본과 문서·검사.
- 운영 클러스터 적용·기존 PVC 삭제·데이터 이전·기존 credential 변경은 하지 않는다.

## 설계
- 운영 namespace는 `minio`, 기존 Worker 지정은 `khplanew01`을 유지한다.
- 서버·mc 이미지와 저장소 입력은 새 MinIO env에서 관리한다. 데이터 볼륨 준비는 명시적으로 수행한다.
- 공용 배포는 공용 namespace의 앱별 RBAC·Ingress를 소유하고 기존 Traefik 감시 범위·VIP를 보존한다.
- Portal API의 S3 주소는 `http://minio.minio.svc.cluster.local:9000`으로 바꾼다. 외부 파일 경로도 MinIO 앱에서 라우팅한다.
- 초기화 버킷 목록은 env 입력으로 분리해 공용 코드를 Portal 버킷 이름과 분리한다.
- local 배포 소유권도 분리하되 기존 namespace·PVC 이름·데이터 경로는 보존한다.
- 기존 운영 설치가 있으면 자동 namespace 이전을 차단하고 별도 이전 안내를 제공한다.

## 실행 단계
- [x] 이미지 설정·외부 registry 조회 및 운영 진단 절차 정리
- [x] 독립 MinIO 설정·검사·배포 명령 구현
- [x] Portal·local 소비 연결 및 앱 카탈로그 정리
- [x] 설치·기존 데이터 이전 문서 정리
- [x] 관련 테스트·렌더·선택 checkout 경계 검사
- [x] 서버 이미지 실제 기동·파일·콘솔 검증 후 배포 설정 반영

## 검증
- `make server-check APP=minio PROFILE=prod` 및 Portal 원본 검사
- MinIO 배포·설정·라우팅·기존 설치 보호 회귀 테스트
- server-checkout·환경변수·local deployment·라우팅 관련 테스트
- `make k8s-check`, `make k8s-render-local`, `git diff --check`

## 위험과 대응
- 위험: namespace 변경으로 기존 PVC가 자동 승계되지 않는다.
- 대응: 기존 운영 리소스가 있으면 새 설치를 차단하고 데이터 백업·복원·연결 전환을 문서화한다.
- 위험: 이미지 다운로드 실패와 저장소 Pending이 rollout을 멈출 수 있다.
- 대응: 운영 이벤트를 확인하고 미러 주소·pull Secret을 env로 받으며 실패 시 Pod/PVC 이벤트 진단 명령을 출력한다.
- 위험: local 공통 원본 경로 변경이 기존 개발 데이터를 초기화할 수 있다.
- 대응: namespace·claimRef·PV·호스트 경로를 유지하고 실제 데이터 변경 없이 렌더로 확인한다.

## 진행 기록
- 2026-10-28: 사용자가 공용 저장소 분리를 요청했다. 진행 중 기존 설치의 rollout 대기 원인 확인을 추가 요청했으며 이미지 직접 주소를 확인하고 운영 이벤트를 요청했다.
- 2026-10-28: `deploy/minio`의 설정·JSON 공통 원본·전용 namespace·독립 CLI와 앱 카탈로그를 추가했다. Portal은 공용 Service를 소비하고 `/minio`와 `/minio-console`은 MinIO 앱 Ingress가 소유한다.
- 2026-10-28: 기존 운영 Deployment/PVC 발견 시 자동 설치를 차단한다. 수동 이전은 백업·Ingress 전환 후 `--allow-legacy`를 명시하며 이전 데이터·PVC·namespace는 자동 삭제하지 않는다. Released PV·이전 claim UID를 자동 복구하지 않는다.
- 2026-10-28: local 소유권을 `local/minio`로 옮기고 기존 namespace·PV/PVC·호스트 경로를 보존했다. API client credential 합성과 공용 middleware 전달 YAML도 갱신했다.
- 2026-10-28: 소스 릴리스와 Docker Hub 검색 결과에는 mc 태그 등록 이력이 있으나, 실시간 Docker Hub 태그 API는 mc·서버 이미지 모두 404, Docker Hub/Quay manifest 조회는 401을 반환했다. 현재 pull 가능한 이미지라고 단정할 수 없어 사내 보관 주소·태그 또는 오류 이벤트를 요청했다. 사내 미러 기본 경로는 설정 예시이며 실제 보유·접근은 확인하지 못했다.
- 2026-10-28: Node 환경·배포·라우팅·선택 checkout 테스트 86개, Python 공용 배포 84개·MinIO 11개·local runtime 5개, 총 186개를 통과했다.
- 2026-10-28: `make server-check APP=all PROFILE=prod`, `make k8s-check`, local/server Kustomize 렌더, 전체 env profile 검사와 `git diff --check`를 통과했다. 실제 클러스터 적용·이미지 pull·기존 데이터 이전은 실행하지 않았다.
- 2026-10-28: 운영 rollout의 직접 원인은 Pod Events 미제공으로 미확정이다. mc는 초기화 Job용이므로 Deployment 대기와 구분해 서버 이미지·PVC·스케줄링을 확인해야 한다.
- 2026-10-28: 추가 요청에 따라 내려받을 수 있는 mc 대체 이미지를 조사했다. `bitnamilegacy/minio-client:2025.7.21-debian-12-r3`의 Docker pull과 셸·mc 실행·mb 도움말·기본 설정 읽기를 실제로 통과했다. digest는 `sha256:73bd39f7899a0cef12b8dd5df13aa93a3ed1aaa44236542442e9ac76819ac158`다. 사내 Docker Hub proxy 경로를 유지하고 mc 이미지 기본값만 교체하며 관련 렌더·테스트를 다시 검사한다. 보관 이미지로 추가 업데이트를 제공하지 않는 배포판임을 문서화한다.
- 2026-10-28: mc 교체 후 MinIO Python 11개와 환경변수·local 배포·초기화 Node 52개, 총 63개 테스트를 통과했다. MinIO 서버 원본 검사·local 전체 설정 검사·local Kustomize 렌더·운영 env/Kustomize 이미지 일치 검사를 통과했다. 사내 proxy 주소는 DNS 접근 불가로 실제 pull하지 못했으며 서버 이미지는 변경하지 않았다.
- 2026-10-28: 서버 이미지 교체 요청에 따라 `bitnamilegacy/minio:2025.7.23-debian-12-r5`를 실제 pull했다. digest는 `sha256:6dabb4a2088c9a79908de3bc05f4586c23ad2182c8908e7e3acbf61c1467fb20`이다. 설정 변경 전에 별도 Docker network·빈 임시 volume에서 검증했으며 테스트 리소스는 종료 후 제거했다.
- 2026-10-28: Bitnami 기본 entrypoint가 기존 `server /data` args와 달라 `command: [minio]`로 native binary를 직접 시작한다. 이전 공식 이미지의 기본 UID가 0인 것을 확인해 `runAsUser: 0`으로 기존 볼륨 접근 권한을 유지한다. 실제 검증도 같은 binary·UID·args·1GiB 메모리 조건으로 수행했다.
- 2026-10-28: live/ready HTTP 200, 현재 mc 초기화 script 두 번 실행, S3 파일 업로드·내용 해시 일치, 저장소 원본 Traefik middleware를 통한 콘솔 HTML/JS·로그인 204와 `/minio/` 다운로드, 컨테이너 재시작 후 파일 보존을 통과했다. 기존 데이터·운영 클러스터는 연결하지 않았다.
- 2026-10-28: 서버 이미지 교체 후 MinIO Python 12개와 환경·local 배포·초기화 Node 52개, 총 64개 검사를 통과했다. `make server-check APP=minio PROFILE=prod`, local Kustomize 렌더·전체 `make k8s-check`, 운영 env/Kustomize 이미지·기동 조건 일치, `git diff --check`를 통과했다. 사내 proxy pull은 미검증이며 운영 클러스터에는 적용하지 않았다. 빈 임시 볼륨에서 검증했으므로 기존 다른 버전 데이터의 호환성은 별도로 확인한다.
- 2026-10-28: 사용자 요청으로 전체 워크트리를 검토하고 main push를 준비했다. origin/main과 HEAD는 같은 커밋이었다. Node 환경·라우팅·배포·선택 checkout 86개와 Python MinIO 12개·공용 배포 84개·local runtime 5개, 총 187개를 통과했다. 전체 서버 원본 검사·env profile 검사·local/server Kustomize 렌더·수정 셸 문법·변경 문서의 로컬 링크·diff 공백 검사를 통과했다.
