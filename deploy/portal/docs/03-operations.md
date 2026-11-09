# Portal 설정 변경과 운영 확인

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**실행 위치:** 관리 호스트의 저장소 루트입니다. 새 터미널에서는 [대상과 입력 확인](01-install.md#1-대상과-입력-확인)에서 사용할 context를 다시 선택합니다. DB schema 변경은 [migration](01-install.md#3-migration)을 따릅니다.

## 5. 설정 변경 반영

최초 설치는 [배포 절차](01-install.md#배포-순서)를 따릅니다. 이미 설치된 Portal에서 env만 변경했다면
해당 입력을 검사하고 Secret으로 등록한 뒤, 아래 표의 Deployment를 재시작합니다.
같은 manifest를 다시 apply하거나 `rollout status`만 실행하면 Secret 변경이 Pod에 반영되지 않습니다.

| 변경 파일 | 검사·Secret 등록의 COMPONENT | 재시작 대상 | 확인할 동작 |
| --- | --- | --- | --- |
| `api.env` | `api` | `api`, `edge-nginx` | API health·로그인, collectstatic 초기화 완료 |
| `web.env` | `web` | `web` | 브라우저 runtime 설정·API 주소·화면 링크 |

각 파일에 대해 `make env-check APP=portal PROFILE=prod COMPONENT=<표의 값>`을 통과한 뒤
같은 COMPONENT와 `KUBE_CONTEXT`로 `make k8s-env`를 실행합니다.

API 설정을 변경한 경우:

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/api
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/edge-nginx
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
```

Web 설정을 변경한 경우에는 다음 블록만 실행합니다. MinIO 서버 설정은 독립 앱의 `make minio-up`을 사용합니다.

```bash
make env-check APP=portal PROFILE=prod COMPONENT=web
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/web
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
```

DB·Keycloak client·MinIO API 계정의 비밀번호를 바꾼다면 해당 서비스의 실제 계정도 먼저 맞춥니다.
Secret 등록과 Pod 재시작만으로 외부 계정이 변경되지는 않습니다.
OIDC client 설정 변경은 [client 등록 절차](01-install.md#keycloak-client-등록),
DB schema 변경은 [migration 단계](01-install.md#3-migration)를 함께 수행합니다. `minio-init`은 버킷 준비용이며,
설정 변경 때마다 다시 실행하지 않습니다.

재시작 후 표의 실제 동작과 [접속 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)을 확인합니다.

## 초기화와 health 검사

MinIO 초기화 Job은 기존 버킷을 유지하고, 버킷 생성의 다른 오류는 실패로 반환합니다.
연결 대기를 포함한 Job 전체 실행 시간은 300초로 제한합니다. 실패한 Job은 원인과 로그를
확인하고 완료된 초기화로 간주하지 않습니다.
최초 설치와 종료된 Job의 재실행 방법은 [공용 MinIO 설치 안내](../../minio/docs/02-operations.md#5-버킷-초기화-재시도)를 따릅니다.

API와 edge-nginx의 readiness/liveness probe는 `Host: localhost`,
`X-Forwarded-Proto: https`를 전달합니다. 운영 HTTPS 강제 전환을 유지하면서
`/api/v1/health/` handler의 응답을 검사하기 위한 설정입니다.
운영 API의 `DJANGO_ALLOWED_HOSTS`에는 실제 Portal DNS와 함께 `localhost`를 포함합니다.
예를 들어 `etch.samsungds.net,api,localhost`로 지정합니다. 누락하면 입력 검사에서 중단하며,
이미 실행 중인 환경에서는 Secret 등록과 API·edge-nginx 재시작 절차로 반영합니다.
