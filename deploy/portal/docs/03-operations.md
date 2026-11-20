# Portal 설정 변경과 운영 확인

[Portal 가이드](../README.md)

설치·업데이트 절차는 [Portal 가이드](../README.md)에 있습니다. 이 문서는 env 변경을 반영할 때 확인할 동작과 health 검사 구성입니다.

- [설정 변경 반영](#설정-변경-반영)
- [health 검사](#health-검사)

## 설정 변경 반영

설치된 Portal의 env 변경을 Secret과 실행 중인 Pod에 반영합니다.

1. [변경] 바꿀 값은 저장소 파일이 아니라 [운영 입력 파일](../../shared/docs/infrastructure/access.md#운영-입력-파일)의 사본([만드는 방법](01-install.md#1-env-파일-작성))에서 바꿉니다. 바꿀 키와 값만 고치고 다른 줄은 그대로 둡니다.
2. [검사] [가이드 B](../README.md#b-업데이트)의 `make portal-check`로 env와 migration 여부를 확인합니다.
3. [변경] `migration:` 줄이 `API 이미지가 같아 생략`이면 가이드 B의 `API env·Web env·manifest` 행의 명령으로 반영합니다. Web env 사본을 쓰면 같은 명령에 `PROD_WEB_ENV_FILE=<Web env 경로>`도 붙입니다.
   성공: 출력에 `Secret 등록 완료: api-env, web-env`와 `Portal 배포 완료`가 있고 JSON 줄이 `"failedStep": null`, `"driftResultCode": 0`입니다.

`portal-up` 단계가 env 검사 → Secret 재등록 → 세 Deployment 재시작 → rollout 대기를 수행합니다. API 이미지가 같으면 migration은 실행하지 않습니다.
같은 manifest를 다시 apply하거나 `rollout status`만 실행하면 Secret 변경이 Pod에 반영되지 않으므로 재시작이 필요합니다.

| 변경 파일 | Secret | Secret을 읽는 Deployment | 확인할 동작 |
| --- | --- | --- | --- |
| `api.env` | `api-env` | `api`, `edge-nginx` | API health·로그인, collectstatic 초기화 완료 |
| `web.env` | `web-env` | `web` | 브라우저 runtime 설정·API 주소·화면 링크 |

재시작 후 표의 동작과 [접속·기능 검증](../../shared/docs/operations/02-deploy.md#접속기능-검증)을 확인합니다. rollout이 끝나지 않으면 Pod event·로그를 확인합니다.

| 함께 바뀌는 대상 | 추가 절차 |
| --- | --- |
| DB·Keycloak client·MinIO API 계정 비밀번호 | [승인] 해당 서비스의 실제 계정을 먼저 변경하고 API env 사본에 같은 값을 넣은 뒤 위 3단계의 Secret 등록과 재시작으로 앱에 반영. DB 계정은 [외부 DB](../../shared/docs/infrastructure/access.md#외부-db), MinIO 접근 키는 [앱 접근 키와 bucket 정책 등록](../../minio/docs/01-configuration.md#앱-접근-키와-bucket-정책-등록)의 방법으로 변경. Portal client secret은 API env 사본의 `OIDC_CLIENT_SECRET`만 바꾸면 같은 명령의 `keycloak-portal-client-setup` 단계가 Keycloak client에 반영 |
| OIDC client 설정 | 같은 명령의 `keycloak-portal-client-setup` 단계가 다시 등록. [Keycloak client 등록](01-install.md#keycloak-client-등록) |
| DB schema | API 이미지가 바뀔 때 실행. [Migration](01-install.md#migration) |
| MinIO 서버 설정·버킷 초기화 | [공용 MinIO](../../minio/README.md) |

## health 검사

API와 edge-nginx의 readiness/liveness probe는 `/api/v1/health/`에 `Host: localhost`, `X-Forwarded-Proto: https`를 전달합니다. 운영 HTTPS 강제 전환을 유지하면서 handler 응답을 검사하기 위한 설정입니다.
운영 API의 `DJANGO_ALLOWED_HOSTS`에는 실제 Portal DNS와 함께 `localhost`를 포함합니다(기본 env: `etch.samsungds.net,api,api.tailwind-internal.svc.cluster.local,localhost`).
누락하면 입력 검사가 `DJANGO_ALLOWED_HOSTS에 운영 health probe의 Host인 localhost를 추가하세요.`로 중단하며, 실행 중인 환경에서는 [설정 변경 반영](#설정-변경-반영)으로 반영합니다.
