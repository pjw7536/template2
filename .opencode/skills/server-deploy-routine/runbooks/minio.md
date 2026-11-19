# MinIO 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `minio` |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/minio` |
| 공개 주소 | S3 `https://s3.etch.samsungds.net`, 콘솔 `https://minio.etch.samsungds.net` |
| 배포 명령 | `make minio-check` → `make minio-up` (성공 시 배포 기록 자동) |
| 완료 기준 | PVC `Bound`, Deployment `Available`, Job `minio-init` `Complete`, 사람이 콘솔 로그인·시험 파일 송수신 확인 |
| 먼저 필요한 것 | 공용 Traefik, 두 host의 공용 TLS, root 계정 값 |

## 사람이 해야 하는 일

- [사람] env의 `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` 실제 값 입력. 기존 운영값은 바꾸지 않음
- [사람] DNS·인증서 파일 준비
- [사람] 앱별 접근 키·bucket 정책 등록(`mc`). 버킷 목록에 이름을 넣는 것만으로 계정이 생기지 않음
- [사람] 콘솔 로그인과 시험 파일 업로드·다운로드 확인

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `MINIO_ENV` | MinIO env 경로 | `deploy/minio/env/prod.env`. 외부 경로면 check·up·drift-check에 같은 값 |
| env 키 | `NODE_NAME`, `MINIO_IMAGE`, `MINIO_CLIENT_IMAGE`, `MINIO_DATA_HOST_PATH`, `STORAGE_SIZE`, `MINIO_API_HOST`, `MINIO_CONSOLE_HOST`, `MINIO_BUCKETS`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | 비밀값은 읽지 않음 |

## A. 최초 설치

1. [사람] root 계정 값·인증서 파일·DNS 준비를 사용자에게 확인합니다.
2. [검사] 공통 사전 검사의 실제 env·원본 결과를 확인합니다. 준비 중 파일이 바뀌었으면 같은 입력으로 재검사합니다.
3. [조회] 노드·저장소 확인
   ```bash
   kubectl --context "<context>" get node khplanew01 -o wide
   kubectl --context "<context>" get storageclass
   kubectl --context "<context>" get pv
   ```
   기존 MinIO PV가 있으면 그 `spec.local.path`가 env의 `MINIO_DATA_HOST_PATH`와 같은지 사용자에게 확인합니다.
4. [변경] 공용 TLS 등록: `s3.etch.samsungds.net`, `minio.etch.samsungds.net` 두 host를 각각 [공통 TLS 등록](00-common.md#공용-tls-등록)으로 등록합니다. 이미 등록돼 있으면 생략합니다.
5. [검사] 공용 진입점 검사
   ```bash
   make ingress-check KUBE_CONTEXT="<context>"
   ```
6. [검사] 배포 전 검사(server dry-run, 변경 없음)
   ```bash
   make minio-check KUBE_CONTEXT="<context>"
   ```
   성공: `MinIO 입력·노드·저장소·TLS·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` 신규 설치면 PV·namespace 생성 예정 안내가 함께 나옵니다.
7. [변경] 배포(승인 필요). namespace·폴더 준비 Job·PV·Secret·Deployment·초기화 Job·Ingress를 만들고 Traefik 감시 범위를 바꿉니다.
   ```bash
   make minio-up KUBE_CONTEXT="<context>"
   ```
   성공: `공용 MinIO 배포 완료: https://minio.etch.samsungds.net/`과 `배포 기록 저장: minio/deploy-record-minio`.
8. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
9. [사람] 콘솔 로그인·시험 파일 송수신과 앱 계정·bucket 정책 등록을 요청합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지·버킷 목록 | A-6 → A-7 → C. 재적용 시 Deployment가 재시작됨. 이미지 변경은 [사람]에게 데이터 호환성·백업을 먼저 확인받음 |
| 인증서 | A-4 |
| 버킷 초기화 재시도 | 아래 블록(승인 필요) |
| 다른 namespace의 기존 MinIO 이전, 데이터 없는 재생성 | 멈추고 사람에게 묻기 |

[변경] 버킷 초기화 재시도: Job이 `Complete` 또는 `Failed`이고 실행 중 Pod가 없을 때만 실행합니다.

```bash
kubectl --context "<context>" -n minio get job minio-init
kubectl --context "<context>" -n minio delete job minio-init
make minio-up KUBE_CONTEXT="<context>"
```

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n minio get pods,pvc,ingress -o wide
kubectl --context "<context>" -n minio get jobs
kubectl --context "<context>" -n minio logs job/minio-init
```

성공: Pod Running(노드 `khplanew01`), PVC Bound, `minio-init` Complete, 공통 마무리의 JSON 판정 `0`.

실패하면 조회합니다.

```bash
kubectl --context "<context>" -n minio describe pods -l app.kubernetes.io/name=minio
kubectl --context "<context>" -n minio describe pvc minio-data
kubectl --context "<context>" -n minio get events --sort-by=.lastTimestamp
```

## 멈추고 사람에게 묻는 조건

- `tailwind-internal`에 기존 MinIO가 있다는 오류(이전 절차 필요, `--allow-legacy`는 사람만)
- PV가 `Released`이거나 경로가 다름, PVC Pending
- 공용 TLS 미등록으로 검사 실패, 이미지 pull 실패
- `minio-init`이 실행 중이거나 반복 실패
- root 계정이 자리표시자라는 검사 오류
- PVC·PV 삭제나 재생성이 필요해 보이는 경우. 실행하지 않습니다.
