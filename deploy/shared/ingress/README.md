# 공용 Ingress 실행 원본

여러 앱이 공유하는 Traefik 리소스와 검사·적용 도구를 관리합니다.
설치·확장·운영 절차는 [공통 배포 절차](../docs/README.md#https인증서)에서 시작합니다.

| 원본 | 역할 |
| --- | --- |
| `stack.yaml`, `kustomization.yaml` | ServiceAccount·RBAC·IngressClass·Deployment·Service와 사내 이미지 매핑 |
| `routing.py` | namespace·운영 배치 보존과 VIP·Worker 후보 검사 |
| `tls.py` | 공용 인증서 등록·검사·갱신과 Traefik 재시작 |
| `manage.py` | 공용 진입점 검사·적용과 Portal 후속 연결 |
| `middlewares/` | 로컬 개발 하위 경로 middleware. 운영은 도메인별 루트 라우팅 |

공유 클러스터에는 루트 Makefile 명령으로만 적용하며, 정적 원본을 `kubectl apply`로 직접 적용하지 않습니다([운영 기준](../docs/ingress/operations.md#적용-명령과-주의)).
