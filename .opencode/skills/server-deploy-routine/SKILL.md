---
name: server-deploy-routine
description: 사내 관리 호스트에서 Kubernetes 앱(공용 Traefik·Keycloak·MinIO·Registry·Airflow·Monitoring·Headlamp·FTP·Portal·권한관리)을 설치·업데이트·재배포하고 env/Secret을 반영하며 이미지를 빌드해 올린다. "설치해줘", "배포해줘", "최신 커밋 반영", "env 바꿨으니 적용", "이미지 빌드해서 올려줘", "인증서 등록" 요청에 적용하고 배포 가이드와 앱 가이드를 따라 준비부터 검증까지 진행한다. 장애 원인 확인은 incident-triage, 준비 여부만 확인은 server-readiness-check, 상태 대조는 deploy-drift-check를 쓴다.
---

# server-deploy-routine

절차의 원본은 사람과 함께 보는 배포 문서다. 이 스킬은 어디를 어떤 순서로 읽을지만 정한다.

## 읽는 순서
1. [배포 가이드](../../../deploy/README.md): 단계 표시, 실행 규칙, 하지 않는 일, 설치 순서, 공통 시작, 공용 TLS·CA 묶음·Traefik·빌드 도구, 마무리, 장애 조회.
2. 대상 앱 가이드(아래 표): 모든 앱이 같은 절을 가진다. `한눈에 보기` → `구성` → `사전 준비` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `문제 해결과 멈춤 조건` → `상세 문서`.
3. 가이드가 가리킬 때만 상세 문서를 연다. 클러스터 밖 단계는 [접근 경로](../../../deploy/shared/docs/infrastructure/access.md)의 해당 절을 연다.
4. checkout을 갱신해 commit이 바뀌었으면 [전환 런북](../../../deploy/shared/docs/operations/05-transition.md)의 `적용 여부 확인`을 먼저 실행하고, 미적용이면 그 문서의 순서를 요청한 배포보다 먼저 수행한다.

## 진행 방법
1. 배포 가이드의 "모든 작업 공통 시작"을 따른다. 앱의 `사전 준비` 표에서 미완료인 준비 작업을 먼저 수행한다.
2. 처음 설치면 앱 가이드의 A, 이미 설치된 앱이면 B에서 변경 종류에 맞는 행을 실행한다. 기본 명령은 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`이며 준비 검사 → 배포 단계 → 대조를 수행한다. `APP`을 빼면 실행되지 않는다.
3. 표시가 있는 단계만 실행한다. 클러스터 밖 단계는 접근 경로의 방법으로 직접 수행하고, 실제로 막혔을 때만 그 절의 `막히면 요청할 것`을 요청한다([실행 규칙](../../../deploy/README.md#실행-규칙)).
4. `make ops-deploy`가 출력한 `{"app":`으로 시작하는 JSON 줄로 성공을 판단한다. `failedStep`이 `preflight`면 `blocked`의 항목을 `reference`의 접근 경로 절로 해결하고 같은 명령을 다시 실행한다. 그 밖의 `failedStep`은 앱 가이드의 `문제 해결과 멈춤 조건`에서 찾는다. `pending`의 남은 일은 마무리에서 처리한다.
5. 여러 앱을 요청받으면 배포 가이드의 설치 순서대로 앱마다 반복하고, 한 앱이 멈추면 그 앱을 먼저 필요로 하는 앱만 건너뛴다.
6. 배포 가이드의 "배포 후 공통 마무리"로 결과를 보고한다.

공용 TLS 등록 또는 이미지 발행만 요청받으면 배포 가이드의 해당 절을 사용한다.

## 앱 가이드

| 앱 | 가이드 | namespace | 먼저 필요한 앱 |
| --- | --- | --- | --- |
| 공용 Traefik(`ingress`) | [deploy/shared/ingress/README.md](../../../deploy/shared/ingress/README.md) | `etch-sso` | 없음 |
| Keycloak | [deploy/keycloak/README.md](../../../deploy/keycloak/README.md) | `etch-sso` | ingress |
| MinIO | [deploy/minio/README.md](../../../deploy/minio/README.md) | `minio` | ingress |
| Registry | [deploy/registry/README.md](../../../deploy/registry/README.md) | `registry` | ingress |
| Airflow | [deploy/airflow/README.md](../../../deploy/airflow/README.md) | `airflow` | ingress, Keycloak, Registry |
| Monitoring | [deploy/monitoring/README.md](../../../deploy/monitoring/README.md) | `monitoring` | ingress |
| Headlamp | [deploy/headlamp/README.md](../../../deploy/headlamp/README.md) | `headlamp` | ingress, Keycloak |
| FTP | [deploy/ftp/README.md](../../../deploy/ftp/README.md) | `etch-ftp` | 없음 |
| Portal | [deploy/portal/README.md](../../../deploy/portal/README.md) | `tailwind-internal` | ingress, Keycloak, MinIO, Registry |
| 권한관리(`iam`) | [deploy/iam/README.md](../../../deploy/iam/README.md) | 없음(Keycloak 설정만) | Keycloak |

의존 관계의 원본은 `deploy/shared/apps.json`의 `dependsOn`이다.

## 원칙
- 필요한 명령이 가이드에 없거나 실제 결과가 기대와 다르면 마지막 성공 단계, 확인된 차이, 재개 명령을 보고한다.
- 저장소 파일을 고치지 않는다. 배포를 막는 원인이 저장소에 있으면 원인·필요한 수정·영향을 보고하고 그 앱만 멈춘다. 운영 기록(`deploy/shared/docs/infrastructure/`)만 고칠 수 있다.
- PV·PVC·namespace·DB를 삭제하지 않는다. 비밀값을 응답과 운영 기록에 옮겨 적지 않는다.
