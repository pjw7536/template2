# 공통 배포 절차

[배포 안내](../../README.md) · [인프라 운영 정보](infrastructure/README.md)

여러 앱이 함께 쓰는 절차의 색인입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 실행 규칙은 [배포 가이드](../../README.md#문서-읽는-법)를 따릅니다.
명령 블록은 따로 적지 않으면 관리 호스트의 저장소 루트에서 실행합니다. 노드나 외부 시스템(DNS·방화벽·LB·인증서 발급)에서 하는 단계는 그 단계에 실행 위치를 적고 [접근 경로](infrastructure/access.md)의 절을 링크합니다.

## 클러스터

| 작업 | 절차 |
| --- | --- |
| 현재 환경 조회 | [서버·노드·네트워크 확인](kubernetes/baseline.md) |
| 새 서버 준비·제어면 구성 | [준비 조건](kubernetes/prerequisites.md) → [CP1~3](kubernetes/control-plane.md) |
| metrics-server 설치 | [metrics-server 설치](kubernetes/control-plane.md#metrics-server-설치) |
| Worker 가입 | [설치·가입·검증](kubernetes/worker.md) |
| API server OIDC 인증 | [API server OIDC](kubernetes/oidc.md) |
| 용어·명령 조회(참고 문서) | [구성 개념](kubernetes/concepts.md), [kubectl](kubernetes/kubectl.md) |

## HTTPS·인증서

| 작업 | 절차 |
| --- | --- |
| 공용 Traefik 설치·갱신·확인 | [ingress 가이드](../ingress/README.md) |
| VIP 구성, backend를 지정한 설치 | [진입점 설치·검증](ingress/setup.md) |
| 운영 중 backend 추가 | [백업·확장·복구](ingress/expand.md) |
| namespace 감시·배치 보존·도메인 라우팅 | [운영 계약](ingress/operations.md) |
| 인증서 파일 준비·추출 | [원본 파일](certificates/prepare.md) → [추출·검증](certificates/extract.md) |
| 공용 TLS 등록 | [배포 가이드의 공용 TLS 등록](../../README.md#공용-tls-등록) |
| 등록 뒤 확인·갱신·CA 신뢰 | [적용·갱신](certificates/apply.md) |

## 배포·운영

| 작업 | 절차 |
| --- | --- |
| 저장소 clone·Git 갱신 | [서버 파일 받기](operations/01-checkout.md) |
| 배포 전 확인·접속과 기능 검증 | [배포 준비와 검증](operations/02-deploy.md) |
| 변경 유형별 반영·Worker 추가·백업 | [운영과 문제 해결](operations/03-operations.md) |
| checkout과 실제 배포 상태 대조·배포 기록·서버 상태 보고 | [배포 상태 대조](operations/04-drift.md) |
| 이미 배포된 서버에 새 checkout 적용 | [전환 런북](operations/05-transition.md) |
| env·Secret 작성·검사·등록 | [앱별 환경설정](configuration/environment.md) |
| 클러스터 밖 작업의 접근 방법 | [접근 경로](infrastructure/access.md) |

실행 원본은 `deploy/shared/ingress`, 인증서 파일은 `deploy/shared/certs`, 앱 설정은 각 앱의 manifest·env·Helm values가 소유합니다.
