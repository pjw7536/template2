# Portal 설정 변경과 운영 확인

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

- [설정 변경 반영](#설정-변경-반영)
- [health 검사](#health-검사)

## 설정 변경 반영

**목적:** 설치된 Portal의 env 변경을 Secret과 실행 중인 Pod에 반영합니다. 최초 설치는 [배포 절차](01-install.md#migration배포검증)를 따릅니다.

**실행 위치:** 관리 호스트의 저장소 루트입니다. 새 터미널에서는 [대상과 입력 확인](01-install.md#1-대상과-입력-확인)의 `KUBE_CONTEXT`를 다시 선택합니다.

같은 manifest를 다시 apply하거나 `rollout status`만 실행하면 Secret 변경이 Pod에 반영되지 않으므로 아래 표의 Deployment를 재시작합니다.

| 변경 파일 | 검사·Secret 등록의 COMPONENT | 재시작 대상 | 확인할 동작 |
| --- | --- | --- | --- |
| `api.env` | `api` | `api`, `edge-nginx` | API health·로그인, collectstatic 초기화 완료 |
| `web.env` | `web` | `web` | 브라우저 runtime 설정·API 주소·화면 링크 |

### 1. API 설정 변경

```bash
make env-check APP=portal PROFILE=prod COMPONENT=api
make k8s-env APP=portal PROFILE=prod COMPONENT=api KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/api
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/api --timeout=10m
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/edge-nginx
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/edge-nginx --timeout=10m
```

### 2. Web 설정 변경

```bash
make env-check APP=portal PROFILE=prod COMPONENT=web
make k8s-env APP=portal PROFILE=prod COMPONENT=web KUBE_CONTEXT="$KUBE_CONTEXT"
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout restart deployment/web
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/web --timeout=10m
```

### 3. 결과 확인

재시작 후 표의 동작과 [접속 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)을 확인합니다. rollout이 끝나지 않으면 Pod event·로그를 확인합니다.

| 함께 바뀌는 대상 | 추가 절차 |
| --- | --- |
| DB·Keycloak client·MinIO API 계정 비밀번호 | 해당 서비스의 실제 계정을 먼저 변경. Secret 등록과 재시작만으로 외부 계정은 바뀌지 않음 |
| OIDC client 설정 | [Keycloak client 등록](01-install.md#keycloak-client-등록) |
| DB schema | [Migration](01-install.md#3-migration) |
| MinIO 서버 설정·버킷 초기화 | [공용 MinIO 운영](../../minio/docs/02-operations.md) |

## health 검사

API와 edge-nginx의 readiness/liveness probe는 `/api/v1/health/`에 `Host: localhost`, `X-Forwarded-Proto: https`를 전달합니다. 운영 HTTPS 강제 전환을 유지하면서 handler 응답을 검사하기 위한 설정입니다.
운영 API의 `DJANGO_ALLOWED_HOSTS`에는 실제 Portal DNS와 함께 `localhost`를 포함합니다(예: `etch.samsungds.net,api,localhost`).
누락하면 입력 검사에서 중단하며, 실행 중인 환경에서는 [API 설정 변경](#1-api-설정-변경) 절차로 반영합니다.
