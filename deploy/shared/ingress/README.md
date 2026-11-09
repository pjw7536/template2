# 공용 Ingress 실행 원본

여러 앱이 공유하는 Traefik 리소스와 검사·적용 도구를 관리합니다.
설치·VIP 확장·운영 기준은 [공용 Ingress 안내](../docs/README.md#https인증서)를 따릅니다.

| 원본 | 역할 |
| --- | --- |
| `stack.yaml`, `kustomization.yaml` | ServiceAccount·RBAC·IngressClass·Deployment·Service와 사내 이미지 매핑 |
| `routing.py` | namespace·운영 배치 보존과 VIP·Worker 후보 검사 |
| `tls.py` | 공용 인증서 등록·검사·갱신과 Traefik 재시작 |
| `manage.py` | 공용 진입점 검사·적용과 Portal 후속 연결 |
| `middlewares/` | file provider가 읽는 공용 경로 middleware |

공유 클러스터의 적용에는 루트 Makefile과 [운영 절차](../docs/ingress/operations.md)를 사용합니다.
정적 원본을 직접 적용하면 namespace 감시·VIP 배치가 기본값으로 바뀔 수 있습니다.
