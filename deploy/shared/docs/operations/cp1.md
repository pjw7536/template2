# CP1 공통 Git·배포 파일 관리

[배포 문서 안내](../../../README.md) · [서버 선택 checkout](../../../SERVER_CHECKOUT.md)

CP1은 저장소를 내려받고 배포 명령을 실행하는 관리 호스트입니다.
Pod와 데이터가 저장되는 Worker는 앱별 배포 정의에 따라 달라집니다.
이 문서는 공통 파일·Git 관리만 설명합니다. 앱 설치·설정 명령은 각 앱의 문서를 따릅니다.

## 파일과 데이터의 위치

| 구분 | 관리 방법 |
| --- | --- |
| Git checkout | `Makefile`, 선택한 `deploy/<app>`, `deploy/shared`, 문서 |
| 앱 env | 해당 앱이 정한 파일 하나를 원본으로 관리. 외부 경로 사용 시 앱 도구에 명시 |
| 인증서·개인키 | [공용 인증서 안내](../../certs/README.md)의 경로·권한·Git 제외 규칙 적용 |
| kubeconfig | 배포 계정의 `$HOME/.kube/config` 또는 조직이 지정한 `KUBECONFIG`. Git에 넣지 않음 |
| 실제 DB·업무 데이터 | 앱의 PV/PVC·Worker·외부 저장소. checkout 복사로 백업되지 않음 |
| 백업 | 앱별 백업·외부 보관·복구 검증 절차를 별도로 준비 |

최초 저장소 준비와 앱 선택은 [서버 선택 checkout](../../../SERVER_CHECKOUT.md)을 따릅니다.
서버 실행에는 기본적으로 `local/`이나 앱 소스가 필요하지 않습니다.

## 갱신 전 확인

배포 checkout 루트에서 다음 명령을 하나씩 실행합니다.

```bash
git status --short
git remote -v
git branch --show-current
git rev-parse HEAD
kubectl config current-context
```

로컬 변경이 있으면 먼저 내용을 확인합니다. 변경을 버리기 위해 강제 초기화하지 않습니다.
대상 브랜치와 원격을 확인한 뒤 갱신합니다.

```bash
git pull --ff-only
git log -1 --oneline
```

개발 PC의 미커밋·미추적 파일은 pull로 전달되지 않습니다.
Git 갱신은 파일만 바꾸며 Kubernetes 리소스·Secret·DB·실행 중인 Pod를 자동 변경하지 않습니다.

## 앱별 반영 안내

| 앱 | 원본 안내 |
| --- | --- |
| Keycloak | [CP1 반영 위치·운영 참고](../../../keycloak/operations/cp1.md), [최초 설치](../../../keycloak/README.md) |
| Airflow | [단계별 실행](../../../airflow/04_SETUP_FLOW.md) |
| Portal | [배포 안내](../../../portal/README.md) |
| FTP | [배포 안내](../../../ftp/README.md) |
| Headlamp | [배포 안내](../../../headlamp/README.md) |
| Monitoring | [배포 안내](../../../monitoring/README.md) |

여러 앱이 공유하는 Traefik·VIP·DNS 상태는 [클러스터 현황](../infrastructure/cluster.md)과
[VIP 안내](../../ingress/VIP.md)를 따릅니다. 앱별 env·Secret·DB 변경은 각 앱이 소유합니다.
