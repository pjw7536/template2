# Portal을 제외한 플랫폼 로컬 실행

[로컬 환경 안내](README.md) · [첫 셋업](../docs/getting-started/01-setup.md) · [서버 배포 안내](../deploy/README.md)

`deploy/shared/apps.json`의 `platform` 그룹인 Keycloak·Airflow·FTP·Monitoring·Headlamp·MinIO를
같은 PC의 kind에서 실행합니다. Portal 이미지 빌드·env 합성·migration·seed·API 호출이 필요하지 않습니다.
기존 `make dev`의 전체 앱 실행 경로도 유지합니다. 두 경로는 같은 kind와 기존 DB·파일을 공유하며,
플랫폼 실행은 이미 설치된 Portal이나 mock을 삭제·종료하지 않습니다.

## 실행과 테스트

Docker, Python 3 + PyYAML, kubectl, OpenSSL이 필요합니다. Helm 3.19 이상과 kind는
`.tools/bin`의 실행 파일도 사용합니다. kind는 `make k8s-tools`가 설치합니다.
Docker 메모리 10GiB·디스크 여유 15GiB 이상을 준비합니다.

```bash
make dev-platform
make k8s-platform-smoke
make k8s-platform-status
```

최초 기동은 Airflow·Monitoring·Headlamp chart가 없으면 공식 외부 배포 경로에서 내려받고,
서버와 같은 lock의 SHA-256을 검사합니다. 공개 registry에 접근할 수 있어야 합니다.
이미지가 준비되어 있으면 Docker 캐시에서 kind로 반입합니다. MinIO 이미지 접근이 제한되면
`LOCAL_MINIO_IMAGE`, `LOCAL_MINIO_CLIENT_IMAGE`로 접근 가능한 같은 버전의 이미지를 지정하거나
`docker load`로 archive를 반입합니다. 사내 registry나 사내 endpoint는 사용하지 않습니다.

```bash
# 준비된 도구·chart·원본만 검사합니다. 클러스터·DB·실제 env는 변경하지 않습니다.
make k8s-platform-check
# 선택 앱을 다시 빌드하거나 배포합니다.
make k8s-platform-rebuild APP=airflow
make k8s-platform-rebuild APP=headlamp
# 전체 kind와 별도 로컬 DB를 종료하며 volume과 파일은 보존합니다.
make down
```

`APP`은 위 6개 앱을 지원합니다. Keycloak·MinIO 갱신은 공용 ingress와 연결된 Headlamp도 함께 갱신합니다.
기존 전체 앱 실행 후 플랫폼의 HTTPS 구성을 다시 적용할 때도 `make dev-platform`을 사용합니다.
`make k8s-smoke`는 기존 Portal 포함 통합 검사이므로 독립 환경에서는 `make k8s-platform-smoke`를 사용합니다.

## 접속과 계정

| 앱 | 주소 | 계정 |
| --- | --- | --- |
| Keycloak 관리 | http://localhost:8180 | `local-keycloak-admin / local-keycloak-admin-change-me` |
| Airflow | http://localhost:8080/airflow | Keycloak `90000001 / dummy-user-change-me` 관리자, `90000003` 운영 |
| Headlamp | https://localhost:8443/headlamp/ | 전용 realm의 `platform-admin`, 미승격 비교용 `platform-viewer` |
| MinIO 콘솔 | http://localhost:8080/minio-console/ | `local/minio/env/minio.env` |
| FTP | localhost:6380, passive 8076–8079 | `ftpuser` |
| Grafana | `make k8s-grafana` → http://localhost:3000 | `admin` |
| Prometheus | `make k8s-prometheus` → http://localhost:9090 | 로컬 port-forward |

생성된 비밀번호는 Git에서 제외된 `local/shared/runtime/credentials.env`에 있습니다.
Headlamp 관리자 비밀번호는 `HEADLAMP_ADMIN_PASSWORD`, 미승격 계정은 `HEADLAMP_VIEWER_PASSWORD`입니다.
이 계정은 서버와 같이 관리자 그룹에 속한 사용자만 Kubernetes 관리 권한을 받는지 비교하기 위한 입력입니다.
미승격 계정은 로그인할 수 있지만 클러스터 자원 조회 권한이 없습니다.

Headlamp와 전용 Keycloak issuer `https://sso.localhost:8443/realms/local-platform`에는 로컬 인증서를 사용합니다.
브라우저에서 사용하려면 `local/shared/runtime/headlamp-tls/ca.crt`를 개발 PC/브라우저의 신뢰 CA로 등록합니다.
도구는 시스템 신뢰 저장소를 자동 변경하지 않습니다. 브라우저의 `.localhost` 해석을 사용하므로 사내 DNS는 필요 없습니다.
CLI smoke는 해당 CA와 로컬 이름 해석을 자체 적용하며 TLS 검증을 끄지 않습니다.

기존 `make k8s-ui`는 `tailwind-local`의 token 방식 Headlamp용 명령입니다.
새 플랫폼 Headlamp는 `headlamp` namespace에 서버와 같은 chart로 설치하며 위 HTTPS 주소로 접속합니다.

## 서버와 공유하는 정의와 로컬 차이

| 앱 | 공유 원본 | 로컬 입력 |
| --- | --- | --- |
| Keycloak | 운영 버전·시작 명령·health probe를 로컬 manifest에서 맞추고 검사 | `local/keycloak/k8s`의 독립 manifest, 별도 Docker DB, localhost 주소, 기존 로컬 realm |
| Airflow | `apps/airflow` 이미지 소스, `deploy/airflow` chart·values·배포·SSO client 도구 | 공개 기반 이미지, 외부 로컬 DB, 적은 자원, 일시정지된 새 DAG |
| FTP | `deploy/ftp/k8s`의 DaemonSet·시작 스크립트 | loopback passive 주소·호스트 포트 |
| Monitoring | `deploy/monitoring` chart·values·배포 도구 | 공개 registry, 적은 지표 보존량 |
| Headlamp | `deploy/headlamp` chart·values·OIDC client 정의·검증 | 로컬 CA·주소·전용 realm·그룹 binding |
| MinIO | `deploy/minio/k8s/base` | 기존 PVC·PV·파일 경로, 로컬 계정·공개 이미지 |

서버와 동일한 이미지·chart 버전과 주요 실행·인증 계약을 테스트하되,
서버의 사내 IdP·TLS 인증서·ODBC driver·registry mirror·실제 업무 API 연결은 별도 서버 검증 대상입니다.
이 로컬 테스트 구성은 deploy 파일을 수정하지 않으며, 기존 배포 정의와 도구를 읽기 전용으로 사용합니다.
Airflow 업무 DAG는 원본 그대로 포함하며 Portal을 호출하는 DAG는 독립 smoke에서 실행하지 않습니다.
로컬 전용 `local_platform_smoke` DAG로 scheduler → LocalExecutor task → metadata DB·로그 기록을 검사합니다.

Headlamp의 실제 ID Token을 API server가 검증하도록 kind control-plane의 static Pod에
전용 issuer·audience·CA와 `headlamp:` 사용자·그룹 prefix를 적용합니다.
다른 OIDC/구조화된 인증 설정이 있으면 덮어쓰지 않고 중단합니다.
최초 적용 전 manifest는 `local/shared/runtime/headlamp-tls/kube-apiserver.before.yaml`에 보관합니다.
기존 Portal/Airflow의 `portal` realm과 기존 사용자·DB·Fernet 키는 보존합니다.

인증 계약 참고: [Headlamp 공식 OIDC 안내](https://headlamp.dev/docs/latest/installation/in-cluster/oidc/).

## 검사 범위와 데이터 보존

smoke는 실제 Headlamp code+PKCE 로그인과 관리자/미승격 RBAC, Keycloak → Airflow 로그인,
독립 DAG 성공, FTP 업로드/다운로드, MinIO 객체 왕복, Grafana DB, Prometheus 실제 Kubernetes 수집을 확인합니다.
고유한 테스트 파일·객체는 정리하고 Airflow DAG의 원래 pause 상태는 복원합니다.
테스트 DAG 실행 이력과 Kubernetes 검사 Job은 확인용으로 남습니다.

포트·데이터 경로 입력은 [기존 로컬 설정 안내](README.md#로컬-설정과-파일-보존)를 따릅니다.
Docker Desktop/WSL 재시작 뒤 worker의 `/data/local-runtime` 마운트가 비었으면 다음 명령으로 복구합니다.

```bash
docker restart tailwind-local-worker
make dev-platform
```

DB·PV·PVC·host 데이터·runtime 파일을 지우거나 kind를 자동 재생성하지 않습니다.
DB volume이 있는데 자격증명 파일이 없으면 재발급 대신 백업 복원을 요구합니다.
kind 포트·마운트 변경으로 재생성이 필요할 때는 기존 안내에 따라 `make down` 후 다시 실행합니다.
