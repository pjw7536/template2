# 공용 Ingress 설치와 운영

[공통 문서](../README.md) · [배포 안내](../../../README.md) · [실행 원본](../../ingress/README.md)

여러 앱이 공유하는 Traefik·APP VIP·HTTPS 라우팅 절차의 시작점입니다.
클러스터 제어면·Worker 가입은 [Kubernetes 안내](../kubernetes/README.md)에서 먼저 진행합니다.
명령은 절차에 지정된 관리 호스트의 저장소 루트에서 실행합니다.

| 하려는 일 | 절차 | 완료 기준 |
| --- | --- | --- |
| 공용 진입점 최초 설치·기존 설치 갱신 | [Traefik 준비·검사·설치](setup.md) | 대상 Worker의 Traefik Ready·실제 앱 HTTPS 응답 |
| VIP·DNS·LB와 앱 연결 관계 확인 | [APP VIP와 앱 HTTPS](vip.md) | Worker 직접 접속·VIP·DNS 응답 일치 |
| 기존 배치를 백업하며 Worker 확장 | [확장·검증·복구](expand.md) | 기존 서비스 유지·신규 backend 검증·복구 입력 확보 |
| namespace 감시·배치 보존·middleware 이해 | [운영 기준과 검사 범위](operations.md) | 적용 명령의 변경 범위와 제한 확인 |
| TLS 인증서 등록·갱신·기존 Secret 이전 | [인증서 적용](../certificates/apply.md) | 공용 TLS 등록·실제 제공 인증서 확인 |

VIP·DNS·backend의 현재 값은 [네트워크 원본](../infrastructure/network.md),
앱별 namespace·주소·배치는 [서비스 원본](../infrastructure/services.md)을 확인합니다.
파일 검사·Pod Ready와 실제 외부 접속 성공은 따로 확인합니다.
