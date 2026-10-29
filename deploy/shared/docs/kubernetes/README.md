# Kubernetes 셋업 가이드

[배포 문서 홈](../../../README.md) · [현재 서버·VIP 정보](../infrastructure/cluster.md)

필요한 작업 하나를 선택해서 진행합니다.

| 작업 | 문서 | 완료 상태 |
| --- | --- | --- |
| CP1~3 셋업 | [01. CP1~3 셋업](01-control-plane.md) | 제어면 3대와 API endpoint 정상 |
| Traefik 셋업 | [02. Traefik 셋업](02-traefik.md) | 선택한 Worker의 공용 HTTPS 진입점 정상 |
| Worker 추가 | [03. Worker 추가](03-worker.md) | 새 Worker 등록·Ready·Pod 네트워크 정상 |

**새 클러스터:** CP1~3 셋업 → Worker 최소 1대 추가 → Traefik 셋업 순서입니다.
**기존 클러스터에 Airflow용 Worker 추가:** 03번만 진행한 뒤 Airflow 배포 문서로 이동합니다.
기존 Traefik을 그대로 사용할 수 있으며 새 Worker를 APP VIP에 추가할 필요는 없습니다.

CP1은 관리 명령을 실행하는 서버이고, Worker는 앱이 실행되는 서버입니다.
각 문서의 실행 위치를 확인합니다. 기존 Ready 노드에 초기화·가입 명령을 반복하지 않습니다.
문서의 명령은 같은 터미널에서 이어서 실행하며, 새 터미널에서는 context 등 입력을 다시 지정합니다.

OS·Kubernetes 설치 도구·버전·CNI는 [서버 현황](../infrastructure/cluster.md)에서 미확인으로 기록되어 있습니다.
실제 값을 먼저 확인하며, OS별 패키지 설치 명령은 그 기준에 맞춰야 합니다.

## 앱 배포와 운영이 필요할 때

- [앱별 시작 문서](../../../README.md#앱별-배포와-상세-작업): Keycloak·Airflow·MinIO 등
- [앱 배포 준비](04-prerequisites.md) → [앱 배포](05-applications.md) → [접속 검증](06-verification.md)
- [업데이트·장애·백업](07-operations.md)

<details>
<summary>설치 기준·개념 참고</summary>

- [Kubernetes 용어](08-concepts.md)
- [현재 환경 조회 명령](09-baseline.md)
- [서버 준비·통신 조건](10-servers.md)
- [클러스터 인수 항목](11-cluster.md)

</details>
