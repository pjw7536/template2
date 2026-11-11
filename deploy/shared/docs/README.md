# 공통 배포 절차

[배포 안내](../../README.md) · [인프라 운영 정보](infrastructure/README.md)

## 클러스터

| 작업 | 절차 |
| --- | --- |
| 현재 환경 조회 | [서버·노드·네트워크 확인](kubernetes/baseline.md) |
| 새 서버 준비·제어면 구성 | [준비 조건](kubernetes/prerequisites.md) → [CP1~3](kubernetes/control-plane.md) |
| metrics-server 설치 | [metrics-server 설치](kubernetes/control-plane.md#metrics-server-설치) |
| Worker 가입 | [설치·가입·검증](kubernetes/worker.md) |
| API server OIDC 인증 | [API server OIDC](kubernetes/oidc.md) |
| 용어·명령 조회 | [구성 개념](kubernetes/concepts.md), [kubectl](kubernetes/kubectl.md) |

## HTTPS·인증서

| 작업 | 절차 |
| --- | --- |
| Traefik·VIP 최초 준비 | [진입점 설치·검증](ingress/setup.md) |
| backend 추가·배치 확장 | [백업·확장·복구](ingress/expand.md) |
| namespace 감시·배치 보존·middleware | [운영 계약](ingress/operations.md) |
| 인증서 준비·추출·등록 | [원본 파일](certificates/prepare.md) → [추출·검증](certificates/extract.md) → [적용·갱신](certificates/apply.md) |

## 배포·운영

| 작업 | 절차 |
| --- | --- |
| 저장소 clone·Git 갱신 | [서버 파일 받기](operations/01-checkout.md) |
| 공통 준비·앱 의존 관계·접속 검증 | [배포 준비와 검증](operations/02-deploy.md) |
| 갱신·장애·백업 | [운영과 문제 해결](operations/03-operations.md) |
| env·Secret 작성·검사·등록 | [앱별 환경설정](configuration/environment.md) |

실행 원본은 `deploy/shared/ingress`, 인증서 파일은 `deploy/shared/certs`, 앱 설정은 각 앱의 manifest·env·Helm values가 소유합니다.
