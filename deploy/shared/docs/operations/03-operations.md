# 운영과 문제 해결

[공통 안내](../README.md#배포운영) · 이전: [배포 준비와 검증](02-deploy.md)

## 업데이트 — 관리 호스트

절차의 원본은 [배포 가이드](../../../README.md)와 각 앱 가이드의 `B. 업데이트`입니다. [모든 작업 공통 시작](../../../README.md#모든-작업-공통-시작)으로 checkout을 갱신하고 현재 상태를 대조한 뒤 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`를 실행합니다. 이 명령은 준비 검사 → 앱 배포 단계(`steps`) → 대조를 수행하고 마지막 줄에 요약 JSON을 출력합니다.
Git 갱신만으로 실행 중인 앱·Secret·DB는 바뀌지 않습니다. 변경 종류에 따라 반영 방식이 다르며, 표시([변경]·[승인])는 앱 가이드 `B. 업데이트`의 같은 행을 따릅니다.

| 변경 | 반영 |
| --- | --- |
| 문서 | 클러스터 적용 불필요 |
| 앱 코드(Airflow·Portal) | [변경] 이미지 tag가 소스 내용으로 자동으로 바뀜 → `ops-deploy`가 `<app>-image` 단계에서 빌드·push한 뒤 배포 |
| Airflow DAG 파일만(공유 폴더 사용) | 재배포 없이 공유 폴더에 반영. [Airflow 가이드](../../../airflow/README.md) |
| manifest·chart 설정·env | [변경] `ops-deploy`. Secret 변경은 Pod 재시작이 있어야 반영되며 각 앱의 `up`이 처리 |
| 저장소 밖 env의 값 | [변경] [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)을 고친 뒤 같은 env 변수(예: `AIRFLOW_ENV=<경로>`)를 붙여 `ops-deploy` |
| 공용 Traefik의 이미지·인자 | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`([ingress 가이드](../../ingress/README.md)). 감시 namespace와 배치는 보존 |
| 공용 Traefik의 backend | [승인] `VIP_BACKENDS=<IP 목록>`을 붙이는 변경. [Traefik·VIP 확장](../ingress/expand.md) |
| 외부 DB·OIDC·MinIO 계정 | 실제 서비스 계정과 앱 설정을 함께 변경. 앱 가이드의 멈춤 조건 |
| TLS 인증서 | [변경] [공용 TLS 등록](../../../README.md#공용-tls-등록). 갱신과 등록 뒤 확인은 [인증서 적용](../certificates/apply.md) |
| 사내 CA | [변경] [사내 CA 묶음](../../../README.md#사내-ca-묶음)을 다시 만들고 묶음을 쓰는 앱을 갱신. API server의 CA는 [승인] [CA 교체](../kubernetes/oidc.md#ca-교체) |
| Portal DB schema | [승인] API 이미지가 바뀌면 `portal-up`이 API를 멈추고 migration. 백업 확인 후 승인([Portal 가이드](../../../portal/README.md#b-업데이트)) |
| DNS·방화벽 | 배포와 따로 진행. [DNS](../infrastructure/access.md#dns), [방화벽](../infrastructure/access.md#방화벽). smoke의 `DNS 미등록`은 배포 실패가 아니며 `ops-deploy` 요약의 `pending`에 남음 |
| chart·Kubernetes·CNI 버전 | 별도 호환성·업그레이드·복구 검증 후 수행 |

여러 앱이 공유하는 Traefik·VIP·DNS의 현재 값은 [네트워크 정보](../infrastructure/network.md), 계약은 [공용 Ingress 운영 기준](../ingress/operations.md)을 따릅니다.
`make <app>-up`이 아닌 명령으로 배포했다면 완료 직후 [배포 기록](04-drift.md#배포-기록-남기기)을 남깁니다. 장애는 [장애 조회](../../../README.md#장애-조회)로 확인합니다.
이미 앱이 배포된 서버가 새 checkout을 처음 받았다면 [전환 런북](05-transition.md)의 `적용 여부 확인`을 먼저 실행합니다.

## Worker 추가

[Worker 추가](../kubernetes/worker.md)에서 프로그램 준비 → 가입 → Ready·네트워크 확인 순서로 진행합니다. 새 서버와 CP1에서 하는 단계는 [노드 SSH](../infrastructure/access.md#노드-ssh)의 방법으로 실행합니다.

- 새 노드의 이름·주소·역할은 [서버·노드](../infrastructure/servers.md)와 [별칭 표](../infrastructure/aliases.json)에 기록합니다.
- 앱 데이터를 둘 Worker면 [Worker 앱 데이터 경로](../infrastructure/operations.md#worker-앱-데이터-경로와-이전)의 디스크 확인을 먼저 합니다.
- 외부 HTTPS 진입점으로도 사용할 때만 [Traefik·VIP 확장](../ingress/expand.md)을 추가로 진행합니다. backend 변경은 [승인] 단계입니다. Traefik이 아직 없는 클러스터면 [Traefik 셋업](../ingress/setup.md)입니다.
- Worker 추가만으로 앱이나 DB가 옮겨지지 않습니다. 앱의 실행 노드는 각 앱 env·manifest의 배치 입력으로 정합니다.

## 백업·복구

| 대상 | 보관·복구 확인 |
| --- | --- |
| 클러스터 | 설치 기준·설정·etcd 백업 → 별도 환경 복구 |
| 앱 DB | 일관성 있는 DB 백업·버전·credential → 별도 DB 복원·로그인·조회 |
| Airflow | DB·Fernet 키·이미지/DAG·설정 → [이전·백업 절차](../../../airflow/README.md)와 시험 실행 |
| 업무 파일·MinIO | 영속 데이터·연결 설정 → 복원 후 업로드·다운로드 |
| 운영 입력 | env·인증서·키·이미지/chart 버전 → 접근 제한된 외부 보관 |

- 백업은 Worker의 원래 디스크와 다른 저장매체에도 보관합니다. 같은 디스크의 다른 폴더에만 복사하면 디스크 장애 때 함께 잃을 수 있습니다.
- 실행 중인 PostgreSQL 데이터 디렉터리를 단순 복사하지 않습니다.
- DB migration이나 CRD를 변경했다면 이미지·Helm revision만 되돌려서는 복구되지 않을 수 있습니다.
- Worker 데이터 경로를 옮길 때는 [데이터 이전 절차](../infrastructure/operations.md#worker-앱-데이터-경로와-이전)를 따릅니다.

**운영 인수 기준:** 백업 담당·보관 위치·주기·복구 목표·복구 시험 결과를 [운영 책임·백업](../infrastructure/operations.md#운영-책임백업인증서)에 기록합니다.
환경별 백업 명령·복구 검증의 미확정 항목도 같은 표에서 관리합니다.
