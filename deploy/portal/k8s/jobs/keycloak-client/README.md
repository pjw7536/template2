# Portal Keycloak client 등록 Job

[Portal 가이드](../../../README.md) · [Keycloak client 등록](../../../docs/01-install.md#keycloak-client-등록)

참고 문서입니다. 운영 agent가 실행하는 절차가 아닙니다.

Portal 전용 client·token mapper·앱 역할·그룹 역할 연결을 준비하는 Kubernetes Job입니다.
Keycloak 자체 realm·사내 IdP 준비를 마친 뒤 사용하며 실제 사용자에게 역할을 자동 부여하지 않습니다.

| 원본 | 역할 |
| --- | --- |
| `job.yaml` | 등록 Job과 관리 입력 참조 |
| `setup-client.sh` | client·신원 claim·`sdwt-groups`·앱 역할 mapper와 `portal-members` 역할 연결 등록 |
| `kustomization.yaml` | Job 적용 진입점 |

운영 입력은 Portal API env(`PROD_API_ENV_FILE`)가 소유하며 Job을 직접 apply하지 않습니다. Secret 준비·Job 실행·검증은
`make ops-deploy APP=portal`의 `keycloak-portal-client-setup` 단계가 수행하고, 이 단계만 다시 실행하는 명령과 성공 문구는 [Keycloak client 등록](../../../docs/01-install.md#keycloak-client-등록)에 있습니다.
