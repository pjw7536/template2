# MinIO 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

여러 앱이 함께 쓰는 공용 MinIO를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 여러 앱이 함께 사용하는 독립 S3 호환 객체 저장소 |
| namespace | `minio` |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/minio` |
| 공개 주소 | S3 `https://s3.etch.samsungds.net`, 콘솔 `https://minio.etch.samsungds.net` |
| 배포 명령 | `make ops-deploy APP=minio` = 준비 검사 → `minio-check` → `minio-up` → `minio-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, PVC `Bound`, Job `minio-init` `Complete` |
| 먼저 필요한 것 | 앱 `ingress`(공용 Traefik), 두 host를 SAN에 가진 인증서 파일 |

## 구성

- 실행: Deployment `minio` 하나가 지정 Worker 한 대에서 실행됩니다. Job `minio-init`이 env의 `MINIO_BUCKETS`를 만들고 이미 있는 버킷은 유지합니다. `minio-up`은 실행할 때마다 이전 `minio-init`을 지우고 다시 실행합니다.
- 접속: 클러스터 내부 S3 SDK는 `http://minio.minio.svc.cluster.local:9000`, 외부 S3 client·브라우저 파일 접근은 `MINIO_API_HOST`의 HTTPS 루트, 콘솔은 `MINIO_BROWSER_REDIRECT_URL`입니다. 두 host는 공용 Traefik(`etch-sso/traefik`)의 HTTPS entrypoint로 들어오며 `minio` namespace에는 TLS 인증서를 등록하지 않습니다. 공용 Traefik은 앱 [ingress](../shared/ingress/README.md)가 배포하고, `minio-up`은 `minio` namespace의 라우팅 권한과 감시만 더합니다.
- 저장: 기본은 지정 Worker의 정적 local PV(`Retain`)이고 `minio-up`이 폴더와 PV를 준비합니다. 동적 StorageClass도 쓸 수 있습니다([저장소](docs/01-configuration.md#저장소)).
- 이미지: [env/prod.env](env/prod.env)의 MinIO 서버·mc 이미지를 Worker가 사내 미러에서 받습니다([이미지](docs/01-configuration.md#이미지)).
- 계정: root 계정은 env의 값으로 Secret `minio-env`에 반영됩니다. 앱별 접근 키·버킷 정책은 각 앱 env에서 관리하고 `mc`로 등록합니다([등록 대상](docs/01-configuration.md#앱-접근-키와-bucket-정책-등록)).

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| 앱 `ingress`(공용 Traefik) 배포([ingress 가이드](../shared/ingress/README.md)) | `make ops-preflight APP=minio KUBE_CONTEXT="<context>"`의 `먼저 필요한 앱 ingress`가 `[통과]` |
| `s3.etch.samsungds.net`·`minio.etch.samsungds.net`이 SAN에 있는 `fullchain.crt`·`private.key`를 `deploy/shared/certs/etch.samsungds.net/`에 배치([인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급)). 공용 TLS 등록은 `ops-deploy`의 준비 검사가 host마다 자동으로 수행 | `make ops-preflight APP=minio KUBE_CONTEXT="<context>"`의 `공용 TLS` 두 줄이 `[통과]` 또는 `[자동 준비]` |
| Worker(`NODE_NAME`)의 `MINIO_DATA_HOST_PATH` 상위 경로가 데이터 디스크에 마운트되고 `STORAGE_SIZE` 이상 여유([저장소](docs/01-configuration.md#저장소)) | `df -hT /appdata`(Worker가 관리 호스트와 같은 서버일 때. 다른 노드면 [노드 SSH](../shared/docs/infrastructure/access.md#노드-ssh)로 실행) |
| DNS 두 host → APP VIP 등록([DNS](../shared/docs/infrastructure/access.md#dns)) | `getent hosts s3.etch.samsungds.net minio.etch.samsungds.net` |

DNS가 아직 없어도 배포는 진행합니다. smoke가 APP VIP로 서비스를 확인해 `DNS 미등록`으로 표시하고, 등록은 `ops-deploy` 요약의 `pending`에 남습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `MINIO_ENV` | MinIO env 경로 | `deploy/minio/env/prod.env`. 다른 값을 쓰면 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)의 경로를 모든 명령에 같게 붙임 |

env 파일의 키입니다.

| 키 | 의미 |
| --- | --- |
| `NODE_NAME` | 설치할 Worker의 hostname label |
| `MINIO_IMAGE` | Deployment의 MinIO 서버 이미지. 고정 tag 또는 digest |
| `MINIO_CLIENT_IMAGE` | `minio-init` Job과 저장 폴더 준비 Job의 mc 이미지. 고정 tag 또는 digest |
| `IMAGE_PULL_SECRET` | `minio` namespace에 준비한 registry 인증 Secret, 불필요하면 빈 값 |
| `STORAGE_CLASS_NAME` | 동적 볼륨 공급자의 실제 이름. 비우면 local PV와 폴더를 자동 준비 |
| `VOLUME_NAME` | 사용할 PV 이름. 비우면 기존 PVC의 연결 이름 또는 신규 `minio-data-pv` |
| `MINIO_DATA_HOST_PATH` | 정적 모드의 Worker 저장 경로. 키가 없으면 `/appdata/minio`. 기존 PV가 있으면 실제 경로와 일치 |
| `STORAGE_SIZE` | PVC 요청 용량(`Gi`·`Ti`) |
| `MINIO_API_HOST` | S3 API 도메인 |
| `MINIO_CONSOLE_HOST` | 콘솔 도메인. `MINIO_API_HOST`와 달라야 함 |
| `MINIO_BROWSER_REDIRECT_URL` | `https://<MINIO_CONSOLE_HOST>/` 형식. 끝에 `/` 포함 |
| `MINIO_SERVER_URL` | MinIO 서버 환경변수. 검사 도구는 클러스터 내부 주소 `http://minio:9000`만 허용 |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | 공용 서버 관리자 계정. 기존 운영값은 보존 |
| `MINIO_BUCKETS` | 초기 생성할 버킷의 쉼표 구분 목록. 공용 코드는 특정 앱 이름을 고정하지 않음 |

root 계정은 env의 값을 그대로 사용합니다. `minio-up`은 실행할 때마다 env의 값으로 Secret `minio-env`를 다시 적용하므로, 이미 설치된 MinIO에 다른 값의 env로 배포하면 root 계정이 바뀝니다. 기존 운영값은 바꾸지 않습니다([root 계정 확인](docs/01-configuration.md#root-계정-확인)).

## A. 최초 설치

1. [검사] 준비 검사로 먼저 필요한 앱 `ingress`와 입력을 확인합니다.
   ```bash
   make ops-preflight APP=minio KUBE_CONTEXT="<context>"
   ```
   성공: `[배포 차단]`으로 시작하는 줄이 없습니다. `[자동 준비]` 줄(공용 TLS 등록)은 2번에서 자동으로 실행됩니다.
   - `[배포 차단] 먼저 필요한 앱 ingress`: [ingress 가이드](../shared/ingress/README.md)의 `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`를 먼저 실행하고 이 검사를 다시 실행합니다.
   - `[배포 차단] 공용 TLS <host>`: 그 host를 SAN에 가진 인증서 파일이 없는 것입니다. [사전 준비](#사전-준비)의 둘째 행을 수행합니다.
   - 그 밖의 `[배포 차단]`: 그 줄의 `볼 곳`에 적힌 [접근 경로](../shared/docs/infrastructure/access.md) 절로 해결합니다.
2. [변경] 배포. 준비 검사(공용 TLS 자동 등록), namespace·저장 폴더·PV 준비, MinIO 기동, 버킷 초기화, Ingress 연결, smoke, 대조를 순서대로 수행합니다.
   ```bash
   make ops-deploy APP=minio KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 단계별 출력은 `MinIO 입력·노드·저장소·TLS·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` → `MinIO 버킷 초기화 대기: job/minio-init` → `공용 MinIO 배포 완료: https://minio.etch.samsungds.net/` → `smoke 통과: minio` 순서입니다.
   - `failedStep`이 `preflight`면 JSON의 `blocked`를 1번과 같은 방법으로 해결하고 같은 명령을 다시 실행합니다.
   - `pending`에 `DNS <host>`가 있으면 배포는 끝난 것입니다. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.
3. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

이미 설치된 MinIO를 업데이트하기 전에 [root 계정 확인](docs/01-configuration.md#root-계정-확인)의 [조회]로 env의 root 계정이 운영 중인 값과 같은지 확인합니다.

| 변경 | 실행 |
| --- | --- |
| env·버킷 목록·manifest | [변경] `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`. Deployment가 다시 시작되고 `minio-init`이 다시 실행됨 |
| 이미지 버전 | [승인] 저장 데이터 형식이 바뀌어 되돌릴 수 없을 수 있습니다. 현재·새 이미지 tag와 [호환성·백업 확인](docs/01-configuration.md#이미지) 결과를 보여 주고 승인받은 뒤 `make ops-deploy APP=minio KUBE_CONTEXT="<context>"` |
| 인증서 갱신 | [변경] 새 파일을 `deploy/shared/certs/etch.samsungds.net/`에 둔 뒤 [공용 TLS 등록](../README.md#공용-tls-등록)의 명령을 `TLS_HOST=s3.etch.samsungds.net`, `TLS_HOST=minio.etch.samsungds.net`으로 한 번씩 실행. 성공: host마다 `공용 TLS 등록 완료: <host>` |
| 버킷 초기화 재시도 | [변경] `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`. `minio-up`이 이전 `minio-init` Job을 지우고 다시 실행하므로 Job을 직접 지우지 않음. 실패 원인 조회는 [버킷 초기화 재시도](docs/02-operations.md#버킷-초기화-재시도) |
| root 계정(`MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`) 변경 | [승인] root 계정을 접근 키로 쓰는 앱의 접속이 끊깁니다. 바뀌는 키 이름과 영향받는 앱을 보여 주고 승인받은 뒤 `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`를 실행하고 그 앱의 env를 같은 값으로 맞춰 재배포 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n minio get pods,pvc,ingress,jobs
kubectl --context "<context>" -n minio logs job/minio-init --tail=20
make minio-smoke KUBE_CONTEXT="<context>"
```

성공: Pod Running, PVC Bound, `minio-init` Complete, `smoke 통과: minio`. 뒤에 `(DNS 미등록 host <n>개)`가 붙으면 서비스는 정상이고 DNS 등록만 남은 것이므로 [DNS](../shared/docs/infrastructure/access.md#dns) 절로 등록합니다.

콘솔 로그인과 파일 업로드·다운로드는 [화면 기능 확인](../shared/docs/infrastructure/access.md#화면-기능-확인) 절의 방법으로 확인합니다. 앱 연동이 요청 범위에 있으면 [앱 접근 키와 bucket 정책](docs/01-configuration.md#앱-접근-키와-bucket-정책-등록)의 등록 대상이 준비됐는지 확인합니다.

## 문제 해결과 멈춤 조건

rollout이 계속 대기할 때의 조회 명령과 이벤트별 확인 내용은 [rollout 진단](docs/02-operations.md#rollout-진단), 모든 앱에 공통인 증상은 [장애 조회](../README.md#장애-조회)에 있습니다. 도구의 오류는 `MinIO 실행 실패: <원인>`으로 출력됩니다.

| 증상 | 원인과 조치 |
| --- | --- |
| smoke `DNS 미등록. APP VIP 직접 접속: …` | 서비스는 정상이고 smoke도 통과. [DNS](../shared/docs/infrastructure/access.md#dns) 절로 두 host를 등록 |
| smoke `DNS 조회 실패, APP VIP 직접 접속도 실패: …` | DNS와 무관하게 서비스에 닿지 않음. [rollout 진단](docs/02-operations.md#rollout-진단)으로 Pod·Ingress를 확인하고 [장애 조회](../README.md#장애-조회)의 404 / 503·TLS 오류 행을 따름 |
| `공용 TLS 마운트가 없습니다`, `deployments.apps "traefik" not found` | 공용 Traefik이 없거나 이전 정의. [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"` 뒤 같은 명령 재실행 |
| `<host>: 공용 TLS 인증서가 없습니다` | 인증서가 등록되지 않음. 파일이 있으면 [변경] `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`의 준비 검사가 등록. 파일이 없으면 [인증서 발급](../shared/docs/infrastructure/access.md#인증서-발급) 절로 준비 |
| `MinIO 대상 노드의 hostname·Ready·스케줄 가능 상태를 확인하세요`, `MinIO 대상 Worker의 차단 taint를 확인하세요` | [조회] `kubectl --context "<context>" get node <NODE_NAME 값>`으로 상태를 확인하고 [장애 조회](../README.md#장애-조회)의 Node NotReady 행을 따름 |
| `실제 값 또는 형식 확인 필요: MINIO_ROOT_USER`(또는 `MINIO_ROOT_PASSWORD`) | env의 root 계정이 자리표시자. 실제 값이 든 env를 [운영 입력 파일](../shared/docs/infrastructure/access.md#운영-입력-파일)로 준비해 `MINIO_ENV=<경로>`로 지정 |
| `기존 PV 경로와 MINIO_DATA_HOST_PATH가 다릅니다` | env의 경로가 기존 PV와 다름. [기존 PV 유지](docs/01-configuration.md#기존-pv-유지)에 따라 env를 기존 PV의 경로에 맞춤. 기존 PV는 바꾸지 않음 |
| `Job 실패: minio/minio-init`, `Job 대기 시간 초과: minio/minio-init` | [버킷 초기화 재시도](docs/02-operations.md#버킷-초기화-재시도)로 원인을 조회하고 다시 배포 |
| 이미지 pull 실패(`ErrImagePull`, `ImagePullBackOff`) | [rollout 진단](docs/02-operations.md#rollout-진단)의 표와 [장애 조회](../README.md#장애-조회)의 ImagePullBackOff 행 |

다음이면 멈추고 보고합니다.

- `기존 PV가 Released·Failed 또는 삭제 중입니다`, `기존 PV가 다른 PVC 또는 이전 PVC UID에 예약되어 있습니다`, `기존 PVC에 연결됐던 PV가 없습니다`, `Bound PV와 현재 MinIO PVC의 연결이 다릅니다`, `기존 MinIO PVC가 삭제 중이거나 Lost 상태입니다`. 기존 데이터가 있습니다. PV·PVC를 지우거나 다시 만들지 않고 `claimRef`를 고치지 않습니다.
- PVC가 `Pending`으로 남음. PV·PVC를 지우거나 다시 만들지 않습니다.
- [root 계정 확인](docs/01-configuration.md#root-계정-확인)에서 `불일치`가 나왔는데 root 계정 변경을 요청받지 않음. 그 env로 배포하지 않습니다. 배포하면 운영 중인 root 계정이 바뀝니다.
- 데이터 경로를 다른 폴더나 다른 Worker로 옮겨야 함. Worker의 데이터 폴더를 옮기거나 지우지 않습니다. 데이터 경로 이전은 [승인] 변경이며 [Worker 데이터 이전](../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전)의 순서를 따릅니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설정과 저장소](docs/01-configuration.md) | 준비 조건, 이미지, 저장소(자동 준비·기존 PV 유지·동적 StorageClass), root 계정 확인, 앱 접근 키와 bucket 정책 등록, 배포 도구의 처리 내용 |
| [운영 작업](docs/02-operations.md) | 버킷 초기화 재시도, rollout 진단 |
