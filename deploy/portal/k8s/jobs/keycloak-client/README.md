# Portal Keycloak client 등록 Job

Portal 전용 client·token mapper·앱 역할·그룹 역할 연결을 준비하는 Kubernetes Job입니다.
Keycloak 자체 realm·사내 IdP 준비를 마친 뒤 사용하며 실제 사용자에게 역할을 자동 부여하지 않습니다.

| 원본 | 역할 |
| --- | --- |
| `job.yaml` | 등록 Job과 관리 입력 참조 |
| `setup-client.sh` | client·신원 claim·`sdwt-groups`·앱 역할 mapper와 `portal-members` 역할 연결 등록 |
| `kustomization.yaml` | Job 적용 진입점 |

운영 입력은 Portal `api.env`가 소유하며 Job을 직접 apply하지 않습니다. Secret 준비·Job 실행·검증은
[Keycloak client 등록](../../../docs/01-install.md#keycloak-client-등록)의 `make keycloak-portal-client-setup`을 따릅니다.
