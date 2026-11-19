---
name: server-deploy-routine
description: 사내 관리 호스트(khplanew01)에서 Kubernetes 앱(Keycloak·MinIO·Registry·Airflow·Monitoring·Headlamp·FTP·Portal)을 설치·업데이트·재배포·env/Secret 갱신하는 운영 절차. 앱별 단계 런북을 따른다. 코드·manifest 수정은 하지 않으며 상태 점검만 필요하면 deploy-drift-check를 쓴다.
---

# server-deploy-routine

## 목적
사내 운영 agent가 저장소를 고치지 않고 앱별 런북의 단계를 순서대로 실행해 배포하게 한다.

## 사용 방법
1. [공통 런북](runbooks/00-common.md)을 먼저 읽는다. 실행 규칙·단계 표시·금지 명령·공통 시작·공용 TLS·배포 후 마무리가 있다.
2. 대상 앱 런북을 연다. 모든 런북은 같은 순서의 절을 가진다: `한눈에 보기` → `사람이 해야 하는 일` → `입력` → `A. 최초 설치` → `B. 업데이트` → `C. 배포 후 확인` → `멈추고 사람에게 묻는 조건`.
3. 공통 런북의 "모든 작업 공통 시작"을 실행한다.
4. 처음 설치면 `A`, 이미 설치된 앱의 변경이면 `B`의 표에서 변경 종류에 맞는 행만 실행한다. 어느 쪽인지 모르면 `make drift-check APP=<app> KUBE_CONTEXT=kubernetes-admin@kubernetes` 결과를 보고 사용자에게 묻는다.
5. 각 단계의 표시를 지킨다: [조회]·[검사]는 바로 실행, [변경]은 명령·대상·영향을 보여 주고 승인 후 실행, [사람]은 사용자에게 요청하고 완료 답을 받은 뒤 진행.
6. 끝나면 `C. 배포 후 확인`과 공통 런북의 "배포 후 공통 마무리"를 실행하고 보고 형식대로 보고한다.

## 앱 런북

| 앱 | 런북 | namespace |
| --- | --- | --- |
| Keycloak | [runbooks/keycloak.md](runbooks/keycloak.md) | `etch-sso` |
| MinIO | [runbooks/minio.md](runbooks/minio.md) | `minio` |
| Registry | [runbooks/registry.md](runbooks/registry.md) | `registry` |
| Airflow | [runbooks/airflow.md](runbooks/airflow.md) | `airflow` |
| Monitoring | [runbooks/monitoring.md](runbooks/monitoring.md) | `monitoring` |
| Headlamp | [runbooks/headlamp.md](runbooks/headlamp.md) | `headlamp` |
| FTP | [runbooks/ftp.md](runbooks/ftp.md) | `etch-ftp` |
| Portal | [runbooks/portal.md](runbooks/portal.md) | `tailwind-internal` |

설치 순서와 의존 관계는 공통 런북의 "앱 설치 순서"를 따른다.

## 원칙
- 런북은 사람용 문서(`deploy/<app>/docs`)의 명령을 요약한 것이다. 런북과 원본 문서가 다르면 원본을 따르고 차이를 보고한다.
- 런북에 없는 명령이 필요하면 원본 문서의 해당 절을 찾고, 없으면 멈추고 묻는다. 명령을 새로 만들지 않는다.
- 저장소 파일을 고치지 않는다. 배포를 막는 원인이 저장소에 있으면 원인·필요한 수정·영향을 보고하고 멈춘다. 운영 기록(`deploy/shared/docs/infrastructure/`)만 고칠 수 있다.
- Secret·env 값을 읽거나 출력하지 않고, PV·PVC·namespace·DB를 삭제하지 않는다.
