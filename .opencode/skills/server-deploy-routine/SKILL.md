---
name: server-deploy-routine
description: 사내 관리 호스트에서 Kubernetes 앱(Keycloak·MinIO·Registry·Airflow·Monitoring·Headlamp·FTP·Portal)을 설치·업데이트·재배포하고 env/Secret을 반영하며 이미지를 빌드해 올린다. "설치해줘", "배포해줘", "최신 커밋 반영", "env 바꿨으니 적용", "이미지 빌드해서 올려줘", "인증서 등록" 요청에 적용하고 배포 가이드와 앱 가이드를 따라 승인 없이 끝까지 진행한다. 장애 원인 확인은 incident-triage, 준비 여부만 확인은 server-readiness-check, 상태 대조는 deploy-drift-check를 쓴다.
---

# server-deploy-routine

절차의 원본은 사람과 함께 보는 배포 문서다. 이 스킬은 어디를 어떤 순서로 읽을지만 정한다.

## 읽는 순서
1. [배포 가이드](../../../deploy/README.md): 단계 표시, 실행 규칙, 하지 않는 일, 설치 순서, 공통 시작, 공용 TLS·CA 묶음·Traefik·빌드 도구, 마무리, 장애 조회.
2. 대상 앱 가이드 `deploy/<app>/README.md`: 모든 앱이 같은 절을 가진다. `한눈에 보기` → `구성` → `사람이 하는 일` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `문제 해결과 멈춤 조건` → `상세 문서`.
3. 가이드가 가리킬 때만 `deploy/<app>/docs/`의 상세 문서를 연다.

## 진행 방법
1. 배포 가이드의 "모든 작업 공통 시작"을 실행한다.
2. 처음 설치면 앱 가이드의 A, 이미 설치된 앱이면 B에서 변경 종류에 맞는 행을 실행한다. 기본 명령은 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`이며 `APP`을 빼면 실행되지 않는다.
3. 단계 표시를 지킨다: [조회]·[검사]·[변경]은 바로 실행, [승인]은 명령·대상·영향을 보여 주고 승인 후 실행, [사람]은 실행하지 않고 멈춰서 요청한다. 앱 가이드 `사람이 하는 일` 표의 일은 `완료 확인` 칸의 명령으로 완료 여부를 먼저 조회한 뒤 미완료일 때만 요청한다. 표시가 어디까지 적용되는지와 `<...>` 자리표시의 값은 배포 가이드의 "단계 표시"에 있다. 표시가 없는 명령 블록은 실행하지 않는다.
4. `make ops-deploy`가 출력한 `{"app":`으로 시작하는 JSON 줄로 성공을 판단한다. 실패하면 `failedStep`의 단계를 앱 가이드의 `문제 해결과 멈춤 조건`에서 찾는다.
5. 여러 앱을 요청받으면 배포 가이드의 설치 순서대로 앱마다 반복하고, 한 앱이 멈추면 그 앱을 먼저 필요로 하는 앱만 건너뛴다.
6. 배포 가이드의 "배포 후 공통 마무리"로 결과를 보고한다.

공용 Traefik·TLS만 요청받으면 배포 가이드의 해당 절만 사용한다. 설치 순서 표의 다른 앱을 함께 배포하지 않는다.

## 앱 가이드

| 앱 | 가이드 | namespace | 먼저 필요한 앱 |
| --- | --- | --- | --- |
| Keycloak | [deploy/keycloak/README.md](../../../deploy/keycloak/README.md) | `etch-sso` | 없음 |
| MinIO | [deploy/minio/README.md](../../../deploy/minio/README.md) | `minio` | 없음 |
| Registry | [deploy/registry/README.md](../../../deploy/registry/README.md) | `registry` | 없음 |
| Airflow | [deploy/airflow/README.md](../../../deploy/airflow/README.md) | `airflow` | Keycloak, Registry |
| Monitoring | [deploy/monitoring/README.md](../../../deploy/monitoring/README.md) | `monitoring` | 없음 |
| Headlamp | [deploy/headlamp/README.md](../../../deploy/headlamp/README.md) | `headlamp` | Keycloak |
| FTP | [deploy/ftp/README.md](../../../deploy/ftp/README.md) | `etch-ftp` | 없음 |
| Portal | [deploy/portal/README.md](../../../deploy/portal/README.md) | `tailwind-internal` | Keycloak, MinIO, Registry |

의존 관계의 원본은 `deploy/shared/apps.json`의 `dependsOn`이다.

## 원칙
- 필요한 명령이 가이드에 없거나 실제 결과가 기대와 다르면 마지막 성공 단계, 확인된 차이, 재개 명령을 보고한다.
- 저장소 파일을 고치지 않는다. 배포를 막는 원인이 저장소에 있으면 원인·필요한 수정·영향을 보고하고 그 앱만 멈춘다. 운영 기록(`deploy/shared/docs/infrastructure/`)만 고칠 수 있다.
- PV·PVC·namespace·DB를 삭제하지 않는다. 비밀값을 응답과 운영 기록에 옮겨 적지 않는다.
