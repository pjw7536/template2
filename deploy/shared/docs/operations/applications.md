# 앱별 배포

[운영 안내](README.md) · 이전: [배포 준비](prepare.md) · 다음: [접속·기능 검증](verify.md)

공통 준비를 마친 뒤 필요한 앱의 README에서 실제 설치 절차를 시작합니다.
이 문서는 의존 관계와 설치 완료 조건을 안내합니다. 실행 명령과 입력은 각 앱의 문서를 원본으로 사용합니다.

## 1. 공용 Traefik

앱보다 먼저 [Traefik 셋업](../ingress/setup.md)을 마칩니다.
공통 Ingress는 앱 env·앱 소스 없이 준비할 수 있습니다.
[APP VIP](../ingress/vip.md)의 Worker backend·인증서와 실제 HTTPS 연결을 확인합니다.
공용 Ingress 준비만으로 앱·DB·앱 Secret이 설치되지는 않습니다.

## 2. Keycloak

[Keycloak 설치 순서](../../../keycloak/README.md#최초-설치-순서)를 따라 서버 배포 → 자체 설정 → 사내 로그인을 확인합니다.
Portal·Headlamp·기본 Airflow SSO는 이 준비를 마친 뒤 각 앱의 client를 연결합니다.
**완료 기준:** DB·Keycloak 정상, 사내 로그인과 사용자 필드 확인. client 등록만으로 사내 로그인 검증을 대신하지 않습니다.

## 3. Airflow

[Airflow 설치 순서](../../../airflow/README.md#최초-설치-순서)에 따라 env·chart·이미지·ODBC·DB/로그 디스크와 기본 Keycloak 로그인을 준비합니다.
`NODE_NAME`은 실제 Worker의 자원·디스크·ODBC 접근과 다른 앱 배치 조건을 확인해 선택합니다.
최초 설치는 새 DB·계정을 준비하고 재배포는 기존 DB 비밀번호·Fernet 키를 보존합니다.
**완료 기준:** DB·scheduler health, UI 로그인. Portal 연동을 사용하면 토큰·API·시험 DAG 결과까지 확인합니다.
신규 DAG는 필요한 것만 검증 후 활성화합니다.

## 4. 운영 도구

| 앱 | 의존 관계와 설치 안내 | 완료 기준 |
| --- | --- | --- |
| [MinIO](../../../minio/README.md) | 공용 Traefik·저장소·이미지·계정. 다른 제품 앱 없이 설치 가능 | PVC Bound·초기화 Job Complete·콘솔·시험 파일 송수신 |
| [Monitoring](../../../monitoring/README.md) | chart·저장소·Grafana 계정. 기본 HTTPS에는 공용 Traefik 필요 | Grafana 로그인·노드 지표·Prometheus target |
| [Headlamp](../../../headlamp/README.md) | Keycloak·TLS/CA·client·관리자 그룹과 모든 API server의 OIDC 인증 | 관리자 접근 허용·별도 권한 없는 비관리자 거부 |
| [FTP](../../../ftp/README.md) | 선택 노드·폴더·포트·계정 파일. 노드 IP로 직접 접속 | passive 접속·파일 송수신·저장 노드 확인 |

MinIO는 Portal이 파일 기능을 사용하기 전에 준비합니다. Monitoring·FTP는 Keycloak 없이 설치할 수 있습니다.
Monitoring의 port-forward는 기본 HTTPS를 사용하지 않는 선택 설정입니다.
Headlamp는 Pod Ready와 client 등록 외에 API server 인증과 사용자 권한 검증까지 필요합니다.

## 5. Portal — 나중에 추가

`platform`으로 기반 앱을 운영했다면 [선택 checkout](checkout.md)을 `all`로 확장합니다.
선택은 이전 범위를 교체하므로 `portal`만 선택해 기존 앱 파일을 제외하지 않습니다.

[Portal 설치 순서](../../../portal/README.md#최초-설치-순서)를 따릅니다.
외부 PostgreSQL·extension, Keycloak, 공용 MinIO·파일 저장소, API/Web·migration 이미지를 먼저 준비합니다.
client 등록 → namespace·Secret·TLS → migration → 앱 → 공용 Traefik 연결 순서는 [배포 절차](../../../portal/docs/03-deploy.md)를 확인합니다.
현재 `make portal-up`은 없으며 안내된 적용 명령을 사용합니다.

**완료 기준:** migration 사후 검사·API health·로그인/callback/logout·파일 업로드/다운로드 확인.
보존할 업무 파일은 `emptyDir` 대신 실제 PVC 등에 연결하고 참고·원본 데이터는 readOnly로 마운트합니다.

공유 클러스터에서는 각 앱의 배포 도구를 사용합니다.
Keycloak 정적 YAML을 직접 적용하면 공용 Traefik의 namespace 감시와 VIP 배치가 기본값으로 돌아갈 수 있습니다.
