# ExecPlan: MinIO 저장소 자동 준비

## 목표
- `make minio-up` 한 번으로 Worker의 저장 폴더, 정적 PV, PVC와 MinIO를 준비한다.
- 기존 PV·PVC와 데이터 경로를 보존하고 `minio-check`는 읽기 전용으로 유지한다.

## 현재 상태
- 정적 모드에서는 사전 생성한 PV가 없으면 배포 도구가 중단된다.
- 기본 Worker는 env의 NODE_NAME이며 앞서 안내한 저장 경로는 /data/minio다.
- 공용 TLS 검사는 이미 배포 전 수행하며 로컬 개발은 별도 PV 정의를 사용한다.

## 범위
- deploy/minio의 env·배포 도구·문서·관련 검사.
- 앱 인증·공용 Traefik·로컬 데이터 경로·다른 앱의 저장소는 변경하지 않는다.

## 설계
- MINIO_DATA_HOST_PATH를 추가하고 기존 env에는 /data/minio 기본값을 적용한다.
- StorageClass가 비어 있으면 PVC의 기존 volumeName, 명시한 VOLUME_NAME, 기본 minio-data-pv 순서로 PV를 결정한다.
- 신규 PV는 local·Retain·ReadWriteOnce이며 minio/minio-data 전용으로 예약한다.
- 기존 PV의 경로·노드·용량·class·claim UID·상태를 검사하고 기존 리소스는 갱신하지 않는다. 기존 PVC가 연결했던 PV가 사라졌으면 새 빈 볼륨으로 대체하지 않는다.
- 대상 Worker에서 일회성 Job의 hostPath DirectoryOrCreate로 폴더를 준비한다. 검증된 mc 이미지와 기존 imagePullSecret을 재사용하고 MinIO credential은 전달하지 않는다.
- 신규 PV에는 DirectoryOrCreate를, 기존 PV에는 Directory를 사용한다. 기존 경로가 사라졌으면 빈 폴더로 대체하지 않는다. 폴더 준비는 쓰기 가능 여부만 검사하며 기존 데이터·소유권·권한을 변경하지 않는다. 완료 Job은 TTL로 정리한다.
- 모든 읽기 검사 후 namespace, 폴더 준비 Job, 신규 PV, 앱 리소스 순서로 적용한다. 신규 PV는 create만 사용해 동시 생성 충돌을 덮어쓰지 않는다.
- 동적 StorageClass 모드에는 PV·폴더 준비 Job을 만들지 않는다.

## 실행 단계
- [x] env·정적 PV 계획과 기존 데이터 보존 검사 추가
- [x] namespace·폴더·PV 자동 준비를 minio-up에 연결
- [x] 신규 설치·재실행·충돌·동적 모드 검사와 문서 갱신
- [x] 서버·선택 checkout·로컬 회귀 및 실제 Kubernetes 저장소 준비 검증

## 검증
- MinIO 단위 검사: 신규 PV, 기존 볼륨 보존, 잘못된 경로·노드·용량·UID, 읽기 전용 check, 준비 Job 실패 시 앱 적용 중단.
- 관련 Node 환경·라우팅·로컬·선택 checkout 검사, server-check APP=minio, env-profile-key-check, k8s-check.
- 임시 로컬 Kubernetes namespace와 PV·전용 경로로 폴더 자동 생성, PV/PVC 결합, 데이터 보존을 확인한다. 기존 개발 리소스는 사용하지 않는다.

## 위험과 대응
- 기존 데이터가 다른 경로로 연결되는 문제: 기존 PVC/PV의 실제 연결을 우선하고 경로·affinity 불일치는 적용 전 중단한다.
- Worker 디스크 선택: env 경로만 사용하며 디스크 포맷·마운트 변경은 자동 수행하지 않는다.
- hostPath Job의 정책·image pull 실패: 제한 시간과 Job 진단 경로를 제공하고 MinIO 앱 적용 전에 중단한다.
- 동시 PV 생성: create 충돌을 보고하며 기존 PV를 덮어쓰지 않는다.

## 진행 기록
- 2026-10-28: 수동 PV 준비 오류와 기존 배포 계약을 확인하고 자동 준비 계획을 작성했다.
- 2026-10-28: 신규 namespace·폴더·PV 자동 준비와 기존 볼륨 보존 검사를 구현했다. 신규 PV는 create만 사용하고 기존 PV에는 apply하지 않는다. 기존 env에는 새 경로의 기본값을 적용한다.
- 2026-10-28: MinIO 단위 검사 27개와 관련 Node 검사 84개가 통과했다. `make server-check APP=minio PROFILE=prod`, `make env-profile-key-check`, `make k8s-check`, `git diff --check`도 통과했다.
- 2026-10-28: kind-tailwind-local의 전용 임시 namespace·PV·Worker 경로에서 실제 준비 Job과 MinIO를 실행했다. 읽기 전용 check의 무변경, 폴더 자동 생성, PV/PVC Bound, 두 번째 배포의 동일 PV/PVC UID 유지, 재시작 후 파일과 경로 권한 보존을 확인했다. 공용 TLS·라우팅은 이 저장소 검증에서 제외했으며 MinIO·mc 이미지는 외부 원본 캐시를 사용했다.
- 2026-10-28: 임시 namespace·PV·저장 파일을 정리했다. 사내 클러스터 적용과 Git 커밋·push는 수행하지 않았다.
- 2026-10-28: 사용자 요청으로 검증한 변경 7개 파일을 main에 커밋·push하는 Git 마무리를 진행한다. 원격 main과 기준 커밋이 같음을 확인했으며 사내 클러스터 배포는 별도로 수행한다.
