# 05. 앱별 배포

[가이드 홈](README.md) · 이전: [공통 준비](04-prerequisites.md) · 다음: [접속 검증](06-verification.md)

명령은 **CP1의 checkout 루트**에서 실행합니다. 04장의 `KUBE_CONTEXT`와 필요한 실제 입력이 준비돼 있어야 합니다.
새 터미널이면 context를 다시 선택합니다. 아래 앱은 필요한 것만 배포합니다.

## 1. 검사와 적용의 차이

| 작업 | 의미 | 보장하지 않는 것 |
| --- | --- | --- |
| `make server-check APP=앱 PROFILE=prod` | 공개 원본·입력 형식·렌더 검사 | 실제 credential·클러스터 기동 |
| 앱별 env/check | 실제 설정 확인; 일부 앱은 클러스터 조회도 수행 | 이미지 pull·로그인 성공 |
| 앱별 up 또는 상세 문서의 apply | 클러스터 리소스 생성·갱신 | 외부 DNS·LB·모든 업무 연동 |
| 06장의 접속·기능 검증 | 사용자의 실제 경로 확인 | 다른 미검증 앱의 정상 여부 |

## 2. Keycloak과 공용 Traefik

[Keycloak 안내](../../../keycloak/README.md)의 env·인증서·Worker 디스크 준비를 마칩니다.
실제 입력을 기본 위치에 두었다면 아래처럼 실행합니다. 외부 입력은 안내의 `KEYCLOAK_ENV`·`KEYCLOAK_CERTS`를
검사와 배포에 동일하게 전달합니다.

APP VIP 최초 구성에서는 [현황](../infrastructure/cluster.md)에 기록된 backend를 인프라 담당자와 확인한 뒤
**유지할 Worker IP 전체**를 쉼표로 입력합니다. 기존 VIP 구성에서 목록을 바꾸지 않는 재배포는
아래 입력을 생략하고 두 명령의 `VIP_BACKENDS` 인자도 생략할 수 있습니다.

```bash
read -r -p 'APP VIP의 전체 Worker backend IP 목록: ' VIP_BACKENDS
make server-check APP=keycloak PROFILE=prod
make keycloak-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make keycloak-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
```

검사가 실패하면 적용 명령을 실행하지 않습니다. 기존 Secret과 입력이 다르다는 오류는 입력 원본과 실제 DB credential을
확인하라는 뜻입니다. Secret·PVC를 지워 우회하지 않습니다. 현재 도구는 기존 namespace 감시와 VIP 배치를 보존합니다.

이후 Keycloak 안내의 **사내 OIDC 연결 → 사용자 claim Job**을 수행합니다.
**완료 기준:** PostgreSQL·Keycloak·Traefik 준비 완료, 해당 도메인의 HTTPS 접속과 사내 로그인 확인.
서버 스택 배포만으로 사내 OIDC·Portal client가 자동 등록되지는 않습니다.

## 3. Portal — 사용할 때

[Portal 입력 안내](../../../portal/README.md) → [운영 overlay 순서](../../../portal/k8s/overlays/prod/README.md)를 따릅니다.
Portal에는 현재 `make portal-up`이 없습니다. 상세 문서의 Secret·Job·overlay 적용이 필요합니다.

1. 외부 PostgreSQL·필요 extension, API/Web 이미지, MinIO와 업무 파일 저장소를 준비합니다.
2. Portal 입력을 검사하고 Keycloak의 [client 등록](../../../portal/k8s/jobs/keycloak-client/README.md)을 완료합니다.
3. Portal namespace·앱 Secret·TLS·PVC 공급을 준비합니다.
4. 실제 API 이미지로 migration Job을 실행하고 완료를 확인합니다.
5. 앱 overlay를 적용하고 공용 Traefik의 Portal 감시를 연결합니다.
6. API health → 로그인/callback/logout → 파일 업로드·다운로드를 확인합니다.

기본 업무 파일 볼륨에 `emptyDir`가 남아 있으면 재생성 시 파일을 보존하지 못합니다.
운영 데이터가 필요한 경로는 해당 overlay에서 실제 PVC 등으로 연결한 후 배포합니다.
Portal 배치 노드는 현재 두 Worker의 자원·스토리지를 보고 확정합니다. 과거 예정 서버를 자동으로 사용하지 않습니다.

## 4. Airflow — 사용할 때

[Airflow 안내](../../../airflow/README.md)의 env·chart·이미지·ODBC·DB/로그 디스크를 준비합니다.
APP VIP 사용 시 [TLS 연결 안내](../../ingress/VIP.md)에 따라 업무 도메인 인증서를 Airflow namespace에 준비합니다.
Ingress를 켠 경로는 기존 공용 Traefik이 필요합니다.

```bash
make server-check APP=airflow PROFILE=prod
make airflow-check KUBE_CONTEXT="$KUBE_CONTEXT"
make airflow-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

외부 env를 쓰면 검사와 배포 양쪽에 `AIRFLOW_ENV=/실제/절대경로`를 지정합니다.
기존 다른 namespace에서 TLS를 최초 복사할 경우 안내의 `AIRFLOW_TLS_SOURCE`를 양쪽에 전달합니다.
Airflow 전용 명령은 Keycloak·Keycloak DB를 재배포하지 않습니다. 신규 DAG는 일시정지로 생성하지만
복원한 DB의 기존 활성 DAG는 별도로 확인합니다.

**완료 기준:** DB·Airflow 준비, `/airflow/health` 응답의 DB·scheduler 상태, UI 로그인 확인.
Portal과 연동할 때는 두 앱의 토큰·API 주소를 맞추고 승인된 시험 DAG의 트리거·결과를 확인한 뒤 업무 DAG를 활성화합니다.

## 5. 선택 운영 도구

| 앱 | 준비·적용 절차 | 완료 기준 |
| --- | --- | --- |
| Monitoring | [전용 안내](../../../monitoring/README.md)의 디스크·chart·관리자 Secret 준비 → `make monitoring-check` → `make monitoring-up KUBE_CONTEXT="$KUBE_CONTEXT"` | Grafana 로그인, Prometheus target·노드 지표 확인 |
| Headlamp | [전용 안내](../../../headlamp/README.md)의 env·chart·선택 TLS 준비 → `make headlamp-check` → `make headlamp-up KUBE_CONTEXT="$KUBE_CONTEXT"` | 조회용 토큰으로 노드·Pod 조회 |
| FTP | [전용 안내](../../../ftp/README.md)의 Worker 경로·포트·Secret·라벨 → 원본 검사·apply | 선택 노드 IP에 passive 접속, 업로드·다운로드 |

Monitoring 기본 접속은 port-forward이며 Headlamp HTTPS는 추가 준비가 필요합니다.
FTP는 APP VIP·Ingress를 사용하지 않습니다. 같은 클러스터의 모든 앱이 같은 접속 경로를 쓰는 것은 아닙니다.

`make server-up`은 기존 Keycloak+Airflow 통합 운용의 호환 경로입니다. 입문 순서는 앱별 명령을 사용합니다.
공용 라우팅을 연결한 뒤 Keycloak 정적 YAML을 직접 적용하면 감시 범위·VIP 배치를 되돌릴 수 있으므로 사용하지 않습니다.
