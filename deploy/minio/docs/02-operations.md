# MinIO 운영 작업

[MinIO 가이드](../README.md) · [설정과 저장소](01-configuration.md)

설치·업데이트 절차는 [MinIO 가이드](../README.md)에 있습니다. 이 문서는 그 밖의 운영 작업입니다. 명령은 관리 호스트의 저장소 루트에서 실행하고, 외부 env를 쓰면 `deploy/minio/env/prod.env` 자리에 그 경로를 넣고 Make 명령에 `MINIO_ENV`로 같은 값을 붙입니다.

- [버킷 초기화 재시도](#버킷-초기화-재시도)
- [rollout 진단](#rollout-진단)

## 버킷 초기화 재시도

`minio-init` Job은 300초 안에 완료되어야 하며 이미 있는 버킷은 유지합니다. 기존 Job은 재배포에서 덮어쓰지 않습니다.

1. 버킷 목록 변경·실패 원인을 해결합니다.
2. [조회] Job이 Complete 또는 Failed이고 활성 Pod가 없는지 확인합니다. 실행 중인 Job을 중복 실행하지 않습니다.
   ```bash
   kubectl --context "<context>" -n minio get job minio-init
   ```
3. [변경] 해당 Job만 삭제하고 다시 배포합니다.
   ```bash
   kubectl --context "<context>" -n minio delete job minio-init
   make minio-up KUBE_CONTEXT="<context>"
   ```

성공: 새 `minio-init`이 `Complete`이며 PVC·버킷 데이터는 삭제되지 않습니다.

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
