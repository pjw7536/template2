# MinIO 운영·이전·재생성

[앱 안내](../README.md) · [설치](01-install.md)

**실행 위치:** 관리 호스트(CP1 등)의 저장소 루트입니다. [서버 입력](01-install.md#2-서버-입력과-이미지)의 `KUBE_CONTEXT`와 `MINIO_ENV`를 export한 Bash 세션을 사용합니다.
이전과 재생성은 대상과 보존할 데이터를 확인한 경우에만 수행합니다.

## 1. 버킷 초기화 재시도

`minio-init` Job은 300초 안에 완료되어야 하며 이미 있는 버킷은 유지합니다. 기존 Job은 재배포에서 덮어쓰지 않습니다.

1. 버킷 목록 변경·실패 원인을 해결합니다.
2. `kubectl --context "$KUBE_CONTEXT" -n minio get job minio-init`로 Job이 Complete 또는 Failed이고 활성 Pod가 없는지 확인합니다. 실행 중인 Job을 중복 실행하지 않습니다.
3. `kubectl --context "$KUBE_CONTEXT" -n minio delete job minio-init`으로 해당 Job만 삭제하고 `make minio-up KUBE_CONTEXT="$KUBE_CONTEXT"`를 다시 실행합니다.

**기대 결과:** 새 `minio-init`이 `Complete`이며 PVC·버킷 데이터는 삭제되지 않습니다.

## 2. 기존 Portal namespace에서 이전

`minio-check`·`minio-up`은 `tailwind-internal`의 기존 MinIO Deployment 또는 PVC를 발견하면 중단합니다. namespace를 바꿔도 PVC·데이터·계정은 자동으로 이전되지 않습니다.
이전 전 진단 명령은 [rollout 진단](01-install.md#6-완료-확인과-rollout-진단)의 namespace를 `tailwind-internal`로 바꿔 사용합니다.

1. 기존 Pod·PVC·이미지·env를 기록하고 현재 rollout 문제를 먼저 해결합니다. PVC·PV는 보존합니다.
2. 앱의 쓰기를 중지하고 객체 데이터와 버킷 정책·계정·서버 설정을 별도로 백업합니다. 버전 관리·보존 정책도 확인합니다.
3. `minio` namespace의 새 볼륨과 공용 Traefik의 TLS를 준비합니다. 기존 볼륨을 두 서버에서 동시에 마운트하지 않습니다.
4. 기존 `tailwind-internal/minio-console` Ingress를 파일로 보관한 뒤 제거해 새 Ingress와 중복되지 않게 합니다.
5. 준비된 이전에서만 아래 명령으로 기존 리소스 검사 예외를 명시합니다. 이 옵션도 기존 리소스를 삭제하지 않습니다.

```bash
python3 deploy/minio/scripts/manage.py check --env "${MINIO_ENV:-deploy/minio/env/prod.env}" \
  --context "$KUBE_CONTEXT" --allow-legacy
python3 deploy/minio/scripts/manage.py up --env "${MINIO_ENV:-deploy/minio/env/prod.env}" \
  --context "$KUBE_CONTEXT" --allow-legacy
```

6. 내부 Service 또는 `kubectl --context "$KUBE_CONTEXT" -n minio port-forward svc/minio 9000:9000` 경로로 백업을 복원하고 파일·계정·정책을 검증합니다.
7. 각 앱의 S3 endpoint를 `http://minio.minio.svc.cluster.local:9000`으로 바꾸고 소비 앱만 갱신합니다.
8. 새 콘솔·파일 경로·앱 업로드를 확인한 뒤 쓰기를 재개합니다. 기존 PV/PVC 정리는 별도 운영 판단으로 남깁니다.

이전 준비 없이 기존 PVC를 지우거나 `kubectl delete namespace tailwind-internal`을 실행하지 않습니다.

## 3. 데이터가 없는 기존 MinIO를 새 경로로 재생성

**대상:** `minio` namespace의 정적 local PV 설치. 기존 버킷·객체·개별 계정·정책을 보존하지 않고 env의 관리자 계정과 `MINIO_BUCKETS`로 초기화합니다.
Keycloak DB·namespace·인증서·registry Secret과 기존 호스트 폴더는 삭제하지 않습니다. `tailwind-internal`에 설치돼 있다면 [2. 기존 Portal namespace에서 이전](#2-기존-portal-namespace에서-이전)을 먼저 확인합니다.

1. `MINIO_ENV`의 `MINIO_DATA_HOST_PATH=/appdata/minio`, `STORAGE_CLASS_NAME=`, `VOLUME_NAME=`을 확인합니다.
   `NODE_NAME`·이미지·관리자 credential은 실제 운영값을 유지합니다. Worker의 `/appdata` 디스크와 새 저장 폴더가 비어 있는지도 확인합니다.
2. 실제 연결을 조회합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n minio get deployment,pvc,job
kubectl --context "$KUBE_CONTEXT" get pv \
  -o custom-columns=NAME:.metadata.name,CLAIM_NAMESPACE:.spec.claimRef.namespace,CLAIM:.spec.claimRef.name,POLICY:.spec.persistentVolumeReclaimPolicy,LOCAL_PATH:.spec.local.path
```

3. 현재 PVC의 PV가 `minio/minio-data` 전용 local PV이며 `Retain`인 경우에만 정리합니다. MinIO로 쓰는 작업이 없고 초기화할 설치인지 확인한 뒤 실행합니다.
   **영향:** Deployment·`minio-init` Job·PVC·PV를 삭제한 뒤 새 PV로 재배포합니다. 호스트 폴더는 삭제하지 않습니다.

```bash
(
  set -euo pipefail
  : "${KUBE_CONTEXT:?운영 context를 지정하세요.}"
  minio_previous_pv="$(kubectl --context "$KUBE_CONTEXT" -n minio get pvc minio-data -o jsonpath='{.spec.volumeName}')"
  [[ -n "$minio_previous_pv" ]]
  minio_previous_binding="$(kubectl --context "$KUBE_CONTEXT" get pv "$minio_previous_pv" -o jsonpath='{.spec.claimRef.namespace}/{.spec.claimRef.name}')"
  minio_previous_policy="$(kubectl --context "$KUBE_CONTEXT" get pv "$minio_previous_pv" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')"
  minio_previous_path="$(kubectl --context "$KUBE_CONTEXT" get pv "$minio_previous_pv" -o jsonpath='{.spec.local.path}')"
  [[ "$minio_previous_binding" == minio/minio-data && "$minio_previous_policy" == Retain && "$minio_previous_path" == /* ]]
  make server-check APP=minio PROFILE=prod
  python3 deploy/minio/scripts/manage.py check --env "${MINIO_ENV:-deploy/minio/env/prod.env}"
  kubectl --context "$KUBE_CONTEXT" -n minio delete deployment minio --wait=true
  kubectl --context "$KUBE_CONTEXT" -n minio delete job minio-init --ignore-not-found --wait=true
  kubectl --context "$KUBE_CONTEXT" -n minio delete pvc minio-data --wait=true
  kubectl --context "$KUBE_CONTEXT" delete pv "$minio_previous_pv" --wait=true
  make minio-check KUBE_CONTEXT="$KUBE_CONTEXT"
  make minio-up KUBE_CONTEXT="$KUBE_CONTEXT"
)
```

**기대 결과:** `minio-up`이 신규 PV·Worker 폴더를 준비하고 `minio-init`이 새 저장소에 `MINIO_BUCKETS`를 생성합니다. PVC `Bound`, PV의 `/appdata/minio`, 콘솔과 테스트 파일 업로드·다운로드를 확인합니다.
**실패 확인:** 권한·이미지 다운로드 등으로 실패하면 원인을 해소하고 `minio-up`을 재실행합니다. `Retain`인 기존 호스트 폴더는 자동 삭제되지 않습니다.

**다음 단계:** 실제 운영 현황과 재생성 결과를 [서비스 원본](../../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에 기록합니다.

## 참고

[Bitnami 서버 이미지](https://hub.docker.com/r/bitnamilegacy/minio/tags), [Bitnami client 이미지](https://hub.docker.com/r/bitnamilegacy/minio-client), [Kubernetes 영구 저장소](https://kubernetes.io/docs/concepts/storage/persistent-volumes/).
