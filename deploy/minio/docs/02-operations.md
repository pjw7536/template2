# MinIO 운영 작업

[MinIO 가이드](../README.md) · [설정과 저장소](01-configuration.md)

설치·업데이트 절차는 [MinIO 가이드](../README.md)에 있습니다. 이 문서는 그 밖의 운영 작업입니다. 명령은 관리 호스트의 저장소 루트에서 실행하고, 외부 env를 쓰면 `deploy/minio/env/prod.env` 자리에 그 경로를 넣고 Make 명령에 `MINIO_ENV`로 같은 값을 붙입니다.

- [버킷 초기화 재시도](#버킷-초기화-재시도)
- [rollout 진단](#rollout-진단)

## 버킷 초기화 재시도

`minio-init` Job은 env의 `MINIO_BUCKETS`를 만들며 이미 있는 버킷은 유지합니다. Job은 300초 안에 완료되어야 하고 `minio-up`은 완료를 330초까지 기다립니다.
`minio-up`은 실행할 때마다 이전 `minio-init` Job을 지우고 새로 실행합니다(출력 `MinIO 버킷 초기화 대기: job/minio-init`). 버킷 목록을 바꿨거나 초기화가 실패했을 때 Job을 직접 지우지 않고 다시 배포하면 됩니다.

초기화가 실패하면 `minio-up`이 `Job 실패: minio/minio-init`(뒤에 Job 로그 끝) 또는 `Job 대기 시간 초과: minio/minio-init`으로 끝납니다.

[조회] 원인을 확인합니다.

```bash
kubectl --context "<context>" -n minio get job minio-init
kubectl --context "<context>" -n minio logs job/minio-init --tail=50
kubectl --context "<context>" -n minio describe job minio-init
```

| 확인 결과 | 조치 |
| --- | --- |
| Pod가 `ErrImagePull`·`ImagePullBackOff` | mc 이미지(`MINIO_CLIENT_IMAGE`) 문제. [rollout 진단](#rollout-진단)의 이미지 행 |
| Job이 기한(300초)을 넘겼고 로그가 `mc alias set` 단계에서 반복 | Job이 `http://minio:9000`에 root 계정으로 접속하지 못함. MinIO Pod가 `Running`인지 [rollout 진단](#rollout-진단)으로 확인 |
| 로그에 `mc mb`의 오류 | 버킷 생성 실패. 로그의 오류 줄을 그대로 보고에 담음 |

원인을 해결한 뒤 [가이드 B](../README.md#b-업데이트)의 `버킷 초기화 재시도` 행으로 다시 배포합니다.

성공: `공용 MinIO 배포 완료`가 출력되고 새 `minio-init`이 `Complete`입니다. PVC·버킷 데이터는 삭제되지 않습니다.

## rollout 진단

[조회] `minio-up`의 `rollout status`가 계속 대기하거나 [가이드 C](../README.md#c-배포-후-확인)가 실패하면 원인을 확인합니다.

```bash
kubectl --context "<context>" -n minio get pods,pvc,ingress -o wide
kubectl --context "<context>" -n minio get jobs -l app.kubernetes.io/name=minio-storage-prepare
kubectl --context "<context>" -n minio describe pods -l app.kubernetes.io/name=minio
kubectl --context "<context>" -n minio describe pvc minio-data
kubectl --context "<context>" -n minio get events --sort-by=.metadata.creationTimestamp
```

정상 상태는 PVC `Bound`, Deployment `Available`, 초기화 Job `Complete`이고 Pod가 `NODE_NAME` Worker에 있는 것입니다.

| 이벤트·상태 | 확인할 입력 |
| --- | --- |
| `ErrImagePull`, `ImagePullBackOff` | 실패한 전체 이미지 주소, 사내 mirror의 tag 보유·인증·CA·Worker 통신 |
| `manifest unknown`, `not found` | 해당 registry에 실제로 보관된 이미지·tag 또는 digest |
| `unauthorized`, `denied` | registry 접근 권한과 `IMAGE_PULL_SECRET` |
| 폴더 준비 Job 실패 | Job Pod Events·이미지·hostPath 정책·실제 저장 경로·쓰기 권한 |
| `FailedScheduling`, PVC `Pending` | PV·StorageClass·용량·accessModes·노드 affinity |
| `CrashLoopBackOff` | MinIO Pod 로그·쓰기 권한·디스크 상태 |

mc 이미지 오류는 초기화·폴더 준비 Job 문제이며 서버 Deployment rollout 대기와 구분합니다.
PVC `Pending`이 풀리지 않거나 PV 재생성이 필요해 보이면 [가이드의 멈춤 조건](../README.md#문제-해결과-멈춤-조건)을 따릅니다.
