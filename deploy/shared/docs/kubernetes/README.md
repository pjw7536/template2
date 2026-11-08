# Kubernetes 클러스터 준비와 조회

[공통 문서](../README.md) · [배포 안내](../../../README.md) · [사내 인프라 정보](../infrastructure/README.md)

클러스터 제어면·노드·네트워크를 준비하거나 실제 상태를 조회할 때 읽습니다.
기존 Ready 노드에는 초기화·가입 명령을 반복하지 않습니다. 각 절차의 실행 위치와 현재 context를 확인합니다.

## 클러스터 설치와 확장

| 작업 | 읽는 순서 | 완료 기준 |
| --- | --- | --- |
| 새 클러스터 구성 | [공통 서버 준비](prerequisites.md) → [CP1~3 구성](control-plane.md) → [Worker 가입](worker.md) → [클러스터 인수 확인](control-plane.md#6-클러스터-인수-확인) | API·노드·시스템 Pod·DNS·Pod/Service 통신·저장소 확인 |
| 기존 클러스터에 Worker 추가 | [설치 기준·프로그램·가입·검증](worker.md) | Ready와 Pod 네트워크 정상 |
| 기존 서버·클러스터 상태 조회 | [현재 환경 확인](baseline.md) | 조회 대상·결과·남은 확인 구분 |

실제 서버·OS·버전·주소는 [인프라 원본](../infrastructure/README.md)과 대상 서버 조회를 대조합니다.
저장소 선언·설치 예시를 실제 운영 적용 상태로 단정하지 않습니다.

## 관련 작업과 참고

| 찾는 내용 | 문서 |
| --- | --- |
| 공용 HTTPS·Traefik·VIP·Ingress 확장 | [공용 Ingress](../ingress/README.md) |
| 앱별 배포 준비·의존 관계·접속 검증·운영 | [공통 앱 배포와 운영](../operations/README.md) |
| Kubernetes 용어와 파일 구조 | [용어·전체 구조](concepts.md) |
| 상태·로그·권한·적용 명령 | [kubectl 참고](kubectl.md) |

새 클러스터는 Worker를 최소 한 대 준비한 뒤 공용 Ingress와 앱을 설치합니다.
