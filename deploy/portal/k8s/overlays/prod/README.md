# Portal 운영 overlay

[앱 안내](../../../README.md) · [환경설정](../../../docs/01-environment.md) · [배포·migration](../../../docs/03-deploy.md)

운영 namespace `tailwind-internal`의 이미지·라우팅·권한과 migration 입력을 관리합니다.
이 overlay는 실제 환경의 이미지·저장소 입력을 채운 뒤 사용하는 템플릿입니다.

## 원본과 입력

| 원본 | 준비할 값·역할 |
| --- | --- |
| `kustomization.yaml` | API·Web registry와 고유 이미지 태그 |
| `migrate/kustomization.yaml` | 앱과 동일한 API 이미지 |
| `namespace.yaml` | Portal namespace |
| `ingress.yaml` | Portal host와 공용 Traefik 라우팅 |
| `traefik-rbac.yaml` | 공용 Traefik의 Portal namespace 조회 권한 |
| `../../base/api.yaml` | 업무 파일 `/data/<domain>` 볼륨과 mount |

기본 API 업무 파일 볼륨은 `emptyDir`입니다. 영속 데이터가 필요한 경로는 실제 PVC로 교체합니다.
참고·원본 데이터는 readOnly로 연결하고 StorageClass/PV·용량·노드 affinity를 확인합니다.
실제 Worker는 Ready·자원·스토리지·Pod/Service 통신을 조회해 선택합니다.

Portal의 `api-env`·`web-env` Secret은 [환경설정 절차](../../../docs/01-environment.md)에서 준비합니다.
인증서는 공용 `etch-sso/traefik-tls`로 관리합니다. Keycloak과 MinIO는 독립 앱이며 이 overlay에서 배포하지 않습니다.

## 적용 순서

실행 명령의 원본은 [배포 절차](../../../docs/03-deploy.md)입니다.
대상·입력 → client 등록·namespace·Secret·TLS → migration → 앱 → 공용 Traefik 연결 → 실제 기능 검증 순서로 진행합니다.
설정만 바꾸는 경우에는 [운영 안내](../../../docs/05-operations.md)를 따릅니다.
