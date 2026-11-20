# MinIO 배포 가이드

[배포 가이드](../README.md) · [공통 절차](../shared/docs/README.md)

여러 앱이 함께 쓰는 공용 MinIO를 설치·운영하는 문서입니다. 단계 표시([조회]·[검사]·[변경]·[승인]·[사람])와 공통 규칙은 [배포 가이드](../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | 여러 앱이 함께 사용하는 독립 S3 호환 객체 저장소 |
| namespace | `minio` |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/minio` |
| 공개 주소 | S3 `https://s3.etch.samsungds.net`, 콘솔 `https://minio.etch.samsungds.net` |
| 배포 명령 | `make ops-deploy APP=minio` = `minio-check` → `minio-up` → `minio-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, PVC `Bound`, Job `minio-init` `Complete` |
| 먼저 필요한 것 | 공용 Traefik, 두 host의 공용 TLS |

## 구성

- 실행: Deployment `minio` 하나가 지정 Worker 한 대에서 실행됩니다. Job `minio-init`이 env의 `MINIO_BUCKETS`를 만들고 이미 있는 버킷은 유지합니다.
- 접속: 클러스터 내부 S3 SDK는 `http://minio.minio.svc.cluster.local:9000`, 외부 S3 client·브라우저 파일 접근은 `MINIO_API_HOST`의 HTTPS 루트, 콘솔은 `MINIO_BROWSER_REDIRECT_URL`입니다. 두 host는 공용 Traefik(`etch-sso/traefik`)의 HTTPS entrypoint로 들어오며 `minio` namespace에는 TLS 인증서를 등록하지 않습니다.
- 저장: 기본은 지정 Worker의 정적 local PV(`Retain`)이고 `minio-up`이 폴더와 PV를 준비합니다. 동적 StorageClass도 쓸 수 있습니다([저장소](docs/01-configuration.md#저장소)).
- 이미지: [env/prod.env](env/prod.env)의 MinIO 서버·mc 이미지를 Worker가 사내 미러에서 받습니다([이미지](docs/01-configuration.md#이미지)).
- 계정: root 계정은 env의 값으로 Secret `minio-env`에 반영됩니다. 앱별 접근 키·버킷 정책은 각 앱 env에서 관리하며 [사람이 `mc`로 등록](docs/01-configuration.md#앱-접근-키와-bucket-정책-등록)합니다.

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.

## 사람이 하는 일

클러스터 밖 작업입니다. 오른쪽 명령으로 완료 여부를 먼저 확인하고, 미완료일 때만 요청합니다.

| 일 | 완료 확인 |
| --- | --- |
| 인증서 파일 배치(두 host가 SAN에 있어야 함) | `ls -l deploy/shared/certs/etch.samsungds.net/fullchain.crt deploy/shared/certs/etch.samsungds.net/private.key` |
| DNS 두 host → APP VIP 등록 | `getent hosts s3.etch.samsungds.net minio.etch.samsungds.net` |
| 선택: 앱별 접근 키·bucket 정책 등록(`mc`), 콘솔 로그인 시험([방법](docs/01-configuration.md#앱-접근-키와-bucket-정책-등록)) | 사용자 보고 |

root 계정은 env의 값을 그대로 사용합니다. 기존 운영값은 바꾸지 않습니다.

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `MINIO_ENV` | MinIO env 경로 | `deploy/minio/env/prod.env`. 외부 경로면 모든 명령에 같은 값 |

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

## A. 최초 설치

1. [검사] 인증서 파일 확인: 위 표의 `ls` 명령.
2. [변경] 공용 TLS 등록: `s3.etch.samsungds.net`, `minio.etch.samsungds.net`을 각각 사이트 폴더 `etch.samsungds.net`으로 [공용 TLS 등록](../README.md#공용-tls-등록)합니다.
3. [변경] 배포
   ```bash
   make ops-deploy APP=minio KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. `공용 TLS 마운트가 없습니다`로 실패하면 [공용 Traefik 갱신](../README.md#공용-traefik-검사갱신)의 `ingress-up` 뒤 다시 실행합니다.
4. [조회] [C. 배포 후 확인](#c-배포-후-확인)

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·버킷 목록 | [변경] `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`. 재적용 시 Deployment가 재시작됨 |
| 이미지 버전 | [승인] 데이터 형식이 바뀔 수 있으므로 승인 후 위 명령 |
| 인증서 | A-2 |
| 버킷 초기화 재시도 | 아래 블록 |

[변경] 버킷 초기화 재시도: Job이 `Complete` 또는 `Failed`이고 실행 중 Pod가 없을 때만 실행합니다.

```bash
kubectl --context "<context>" -n minio get job minio-init
kubectl --context "<context>" -n minio delete job minio-init
make minio-up KUBE_CONTEXT="<context>"
```

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n minio get pods,pvc,ingress,jobs
kubectl --context "<context>" -n minio logs job/minio-init --tail=20
make minio-smoke KUBE_CONTEXT="<context>"
```

성공: Pod Running, PVC Bound, `minio-init` Complete, `smoke 통과: minio`.

## 문제 해결과 멈춤 조건

rollout이 계속 대기할 때의 조회 명령과 이벤트별 확인 내용은 [rollout 진단](docs/02-operations.md#rollout-진단), 모든 앱에 공통인 증상은 [장애 조회](../README.md#장애-조회)에 있습니다.

멈추고 사람에게 묻는 조건입니다.

- PV가 `Released`이거나 경로가 다름, PVC Pending
- 이미지 pull 실패, `minio-init` 반복 실패
- root 계정이 자리표시자라는 검사 오류
- PVC·PV 삭제나 재생성이 필요해 보이는 경우. 실행하지 않습니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [설정과 저장소](docs/01-configuration.md) | 준비 조건, 이미지, 저장소(자동 준비·기존 PV 유지·동적 StorageClass), 앱 접근 키와 bucket 정책 등록, 배포 도구의 처리 내용 |
| [운영 작업](docs/02-operations.md) | 버킷 초기화 재시도, rollout 진단 |
