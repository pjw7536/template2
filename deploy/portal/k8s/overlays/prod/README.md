# Portal 운영 overlay

[Portal 가이드](../../../README.md) · [환경설정](../../../docs/01-install.md#환경설정) · [Migration](../../../docs/01-install.md#migration)

운영 namespace `tailwind-internal`의 이미지·라우팅·권한과 migration 입력을 관리합니다.
이미지 tag `auto`는 배포 도구(`deploy/portal/scripts/up.py`)가 `apps/portal` 소스 내용으로 정한 tag로 바꿉니다. `kubectl apply -k`로 직접 적용하지 않고 `make portal-up`을 사용합니다.

## 원본과 입력

| 원본 | 준비할 값·역할 |
| --- | --- |
| `kustomization.yaml` | API·Web registry. `newTag: auto`는 자동 tag, 고정하려면 실제 tag |
| `migrate/kustomization.yaml` | 앱과 동일한 API 이미지 |
| `namespace.yaml` | Portal namespace |
| `ingress.yaml` | Portal host와 공용 Traefik 라우팅 |
| `traefik-rbac.yaml` | 공용 Traefik의 Portal namespace 조회 권한 |
| `../../base/api.yaml` | 업무 파일 `/data/<domain>` 볼륨과 mount |

기본 API 업무 파일 볼륨은 `emptyDir`입니다. 영속 데이터가 필요한 경로는 실제 PVC로 교체합니다.
참고·원본 데이터는 readOnly로 연결하고 StorageClass/PV·용량·노드 affinity를 확인합니다.
실제 Worker는 Ready·자원·스토리지·Pod/Service 통신을 조회해 선택합니다.

Portal의 `api-env`·`web-env` Secret 입력은 [환경설정](../../../docs/01-install.md#환경설정), 등록은 `portal-up`이 수행합니다.
인증서는 공용 `etch-sso/traefik-tls`로 관리합니다. Keycloak과 MinIO는 독립 앱이며 이 overlay에서 배포하지 않습니다.

## 적용 순서

실행 명령의 원본은 [Portal 가이드](../../../README.md#a-최초-설치)입니다.
`make ops-deploy APP=portal`이 이미지 → client 등록 → 검사 → namespace·Secret·migration·앱·공용 Traefik 연결 → smoke 순서로 진행합니다([단계별 동작](../../../docs/01-install.md#배포-단계와-도구-동작)).
설정만 바꾸는 경우에는 [설정 변경 반영](../../../docs/03-operations.md#설정-변경-반영)을 따릅니다.
