# Portal 설정 변경과 운영 확인

[Portal 가이드](../README.md)

설치·업데이트 절차는 [Portal 가이드](../README.md)에 있습니다. 이 문서는 env 변경을 반영할 때 확인할 동작과 health 검사 구성입니다.

- [설정 변경 반영](#설정-변경-반영)
- [health 검사](#health-검사)

## 설정 변경 반영

설치된 Portal의 env 변경을 Secret과 실행 중인 Pod에 반영합니다. [사람]이 env 파일을 고친 뒤 [가이드 B](../README.md#b-업데이트)의 명령으로 반영합니다.

[변경]

```bash
make ops-deploy APP=portal KUBE_CONTEXT="<context>"
```

`portal-up` 단계가 env 검사 → Secret 재등록 → 세 Deployment 재시작 → rollout 대기를 수행합니다. API 이미지가 같으면 migration은 실행하지 않습니다.
같은 manifest를 다시 apply하거나 `rollout status`만 실행하면 Secret 변경이 Pod에 반영되지 않으므로 재시작이 필요합니다.

| 변경 파일 | Secret | Secret을 읽는 Deployment | 확인할 동작 |
| --- | --- | --- | --- |
| `api.env` | `api-env` | `api`, `edge-nginx` | API health·로그인, collectstatic 초기화 완료 |
| `web.env` | `web-env` | `web` | 브라우저 runtime 설정·API 주소·화면 링크 |

재시작 후 표의 동작과 [접속·기능 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)을 확인합니다. rollout이 끝나지 않으면 Pod event·로그를 확인합니다.

| 함께 바뀌는 대상 | 추가 절차 |
| --- | --- |
| DB·Keycloak client·MinIO API 계정 비밀번호 | [사람] 해당 서비스의 실제 계정을 먼저 변경. Secret 등록과 재시작만으로 외부 계정은 바뀌지 않음 |
| OIDC client 설정 | 같은 명령의 `keycloak-portal-client-setup` 단계가 다시 등록. [Keycloak client 등록](01-install.md#keycloak-client-등록) |
| DB schema | API 이미지가 바뀔 때 실행. [Migration](01-install.md#migration) |
| MinIO 서버 설정·버킷 초기화 | [공용 MinIO](../../minio/README.md) |

## health 검사

API와 edge-nginx의 readiness/liveness probe는 `/api/v1/health/`에 `Host: localhost`, `X-Forwarded-Proto: https`를 전달합니다. 운영 HTTPS 강제 전환을 유지하면서 handler 응답을 검사하기 위한 설정입니다.
운영 API의 `DJANGO_ALLOWED_HOSTS`에는 실제 Portal DNS와 함께 `localhost`를 포함합니다(예: `etch.samsungds.net,api,localhost`).
누락하면 입력 검사에서 중단하며, 실행 중인 환경에서는 [설정 변경 반영](#설정-변경-반영)으로 반영합니다.
