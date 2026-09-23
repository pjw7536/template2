# 공용 Ingress 진입점

[배포 문서 안내](../../README.md)

이 폴더는 기존 Traefik의 설정 소유권을 공용으로 분리합니다.
기본 실행 위치는 기존 `etch-sso` namespace, `khplane01w09` worker이며 80/443을 사용합니다.
현재 APP VIP 환경은 [두 Worker 443 연결 안내](VIP.md)에 따라 동일 Deployment를 두 replica로 확장합니다.
새 Worker를 추가하거나 앱 재배포 없이 Traefik만 확장할 때는 [Worker 추가 가이드](ADD_WORKER.md)를 따릅니다.

| 파일 | 역할 |
| --- | --- |
| `stack.yaml` | 기존 Traefik ServiceAccount·RBAC·IngressClass·Deployment·Service |
| `kustomization.yaml` | 기존 namespace와 사내 이미지 매핑 |
| `routing.py` | namespace 감시 보존·앱별 권한·VIP Backend 노드 배치 검사 및 구성 |
| `VIP.md` | 확정된 APP VIP·업무 DNS·인증서·서버 실행 및 접속 검증 절차 |
| `ADD_WORKER.md` | 새 Worker 등록·Traefik 단독 확장·LB 활성화·검증·복구 절차 |

Keycloak Kustomize 진입점도 이 원본을 참조합니다. 정적 전달 YAML은 `deploy/keycloak/export`에서
운영 설정(2개 replica, RollingUpdate, `etch-sso,headlamp` 감시, `ingress: traefik` 노드 선택)을 추가합니다.
정적 기본값은 `etch-sso` 단독 감시이며 기존 Keycloak 단독 설치와 호환됩니다.
권장 경로는 [앱별 배포](../docs/kubernetes/05-applications.md)의 `keycloak-up`, `airflow-up`입니다.
Keycloak 도구는 기존 감시 범위를 보존하고 Airflow 도구는 자기 namespace의 권한과 감시를 추가합니다.
`make server-up`은 [서버 기동 안내](../docs/operations/server-start.md)의 기존 통합 운용을 위한 호환 명령입니다.
기존 Portal 등 다른 namespace를 제거하지 않고, 이미 전체 namespace를 감시하는 경우 범위를 좁히지 않습니다.

최초 `VIP_BACKENDS=10.172.40.117,10.172.40.87`을 지정하면 두 IP의 Node를 조회해 각 Worker에 Traefik 하나씩 배치합니다.
Backend 목록은 `deploy.tailwind.local/vip-backends` Deployment annotation에 기록하며 이후 인자를 생략해도 유지합니다.
현재 단독 소스·이미지·hostPort는 그대로 사용하고 앱·DB의 nodeSelector는 변경하지 않습니다.

Airflow는 자기 namespace의 Ingress·TLS Secret과 Helm 설정을 소유합니다.
Portal 전용 Nginx를 거치지 않고 같은 controller가 `/airflow`를 Airflow Service로 전달합니다.
TLS는 사용 도메인에 맞는 인증서여야 하며 앱 namespace에 존재해야 합니다.

`kubectl apply -k deploy/shared/ingress`는 단독 기본값을 적용하고 Keycloak 전달 YAML은 고정된 운영 설정을 적용하므로,
공용 앱을 연결한 서버에서는 앱별 `keycloak-up` 또는 `airflow-up`을 사용합니다. 이 구분은 라이브 클러스터의 설정을 보존하기 위한 것입니다.

[Traefik Kubernetes Ingress 설정](https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-ingress/)에서 namespace 감시와 IngressClass 동작을 확인할 수 있습니다.
