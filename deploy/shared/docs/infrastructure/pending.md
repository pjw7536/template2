# 서버 적용 대기 작업

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

저장소 선언·확정된 목표와 실제 사내 서버 상태가 아직 맞지 않아 **서버에서 수행해야 하는 작업**의 목록입니다.
값의 원본은 각 행의 원본 문서이며 이 문서에는 작업·현재 상태·절차만 둡니다. 기록 형식은 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.

- 적용과 확인 결과는 [운영 기록](../operations/01-checkout.md#운영-기록)에 남기는 것을 권장합니다. 공유 원본을 갱신할 때는 근거를 확인한 뒤 해당 값을 갱신하고 완료된 행을 삭제합니다.
- 새 작업은 해당 분류에 행을 추가합니다. 주체가 정해지지 않았으면 `미확인`으로 둡니다.
- 주체는 운영 책임의 참조입니다. 요청받은 작업은 운영 agent가 [접근 경로](access.md)의 방법으로 직접 수행하고, 접근이 실제로 막혔을 때만 그 절의 `막히면 요청할 것`을 요청합니다.
- 상태의 `미확인`은 서버 조회·사용자 확인이 없다는 뜻이며 미적용으로 단정하지 않습니다. 작업 전 실제 상태를 조회합니다.

## 1. 네트워크·DNS·인증서

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 운영 SSO DNS 전환 | `sso.etch.samsungds.net` → APP VIP | 현재 DNS는 `etch-sso.samsungds.net` → `khplane01w09` 주소. 새 주소 등록 미확인 | [전환·계획 주소](network.md#전환계획-주소) | 사용자 |
| 앱별 DNS 등록 | 서비스 주소 표의 앱 도메인 → APP VIP | 미확인 | [서비스 접속 주소](services.md#서비스-접속-주소), [DNS 명명](network.md#dns-명명과-향후-구역-위임) | 사용자 |
| 업무 인증서 추가 신청·발급 | DNS SAN 92개·IP SAN 1개 | 신청안 작성. 제출·발급 미확인 | [업무 HTTPS 인증서](network.md#업무-https-인증서) | 미확인 |
| 공용 TLS 등록 | 발급 인증서를 공용 Traefik 저장소에 등록(앱 배포의 준비 검사가 host별로 등록) | 미확인 | [공용 TLS 등록](../../../README.md#공용-tls-등록) | 운영자 |
| 사내 이미지 저장소 DNS 등록 | `store.etch.samsungds.net` → APP VIP | 미확인 | [전환·계획 주소](network.md#전환계획-주소) | 사용자 |
| 사내 이미지 저장소 공용 TLS 등록 | `store.etch.samsungds.net`용 인증서를 공용 Traefik에 등록(Registry 배포의 준비 검사가 인증서 파일이 있으면 등록) | 등록·VIP 제공 미확인 | [Registry 사전 준비](../../../registry/README.md#사전-준비) | 운영자 |
| FTP 방화벽 개방 | 허용 출발지 → FTP 노드 TCP `6380`, `8076–8079` | 미확인 | [FTP 직접 접속](network.md#ftp-직접-접속) | 미확인 |

## 2. 클러스터·공통 구성

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 관리 호스트 준비 | `khplanew01`에 admin kubeconfig·저장소 전체 checkout과 kubectl·helm·chart·외부 env를 두고 `make drift-check` 실행. 이미지 빌드용 nerdctl·BuildKit은 `make build-tools-install`로 설치 | 미확인 | [관리 호스트 준비](../operations/04-drift.md#관리-호스트-준비) | 운영자 |
| 공용 Traefik(`ingress`) 배포 기록 | `make ops-deploy APP=ingress`로 배포 기록 생성. 이미 Traefik이 있으면 [전환 런북](../operations/05-transition.md) | 미확인 | [ingress 가이드](../../ingress/README.md) | 운영자 |
| 공용 Traefik·APP VIP backend | backend 2대에서 Traefik이 443 응답 | 저장소 기본 배치는 `khplane01w09` 1대. 실제 배치·LB 응답 미확인 | [VIP와 backend](network.md#vip와-backend), [backend 확장](../ingress/expand.md) | 운영자 |
| 사내 미러 pull 확인 | 서버가 받는 모든 이미지·패키지를 대상 노드에서 받을 수 있음 | 미확인 | [서버가 받는 이미지](repositories.md#서버가-받는-이미지), [패키지 주소](repositories.md#패키지chartartifact-주소) | 운영자 |
| API server 버전 확인 | 실제 버전을 서버 현황에 반영 | CP1 확인값 `v1.36.0`, metrics-server 안내에는 1.36.4로 기록되어 충돌 | [설치 기준](servers.md#확인된-worker-설치-기준), [metrics-server](../kubernetes/control-plane.md#metrics-server-설치) | 운영자 |
| 사내 이미지 저장소 배포 | Zot `Running`, Traefik `websecure` 읽기 제한 600초 적용(`make ops-deploy APP=ingress`), 노드·빌드 호스트의 사내 CA 신뢰와 HTTPS push·pull 성공 | 미확인 | [registry 설치](../../../registry/README.md) | 운영자 |
| metrics-server 설치 | `kubectl top` 동작 | 미확인 | [metrics-server 설치](../kubernetes/control-plane.md#metrics-server-설치) | 운영자 |
| API server OIDC 인증 | Headlamp 사용자 토큰으로 Kubernetes API 인증 | 미확인 | [API server OIDC](../kubernetes/oidc.md) | 운영자 |

## 3. 앱 배포

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| Keycloak 배포·공개 주소 | `sso.etch.samsungds.net`에서 realm `etch` 로그인 | 저장소는 새 주소 선언. 서버 적용·접속 미확인 | [Keycloak 배포](../../../keycloak/README.md), [서비스 배치](services.md#앱별-배치와-스토리지-선언) | 운영자 |
| MinIO 배포 | `/appdata/minio` 저장소로 설치하고 콘솔·API 접속 | 배포·접속 미확인 | [MinIO 설치](../../../minio/README.md), [서비스 배치](services.md#앱별-배치와-스토리지-선언) | 운영자 |
| 이미지 빌드 도구 설치 | 관리 호스트에 nerdctl·BuildKit 설치(`make build-tools-install`, 비밀번호 없는 sudo 필요)와 사내 이미지 저장소 인증서 신뢰 | 미확인 | [빌드 도구 준비](../../../airflow/docs/02-artifacts.md#containerd-빌드-도구-준비) | 운영자 |
| Airflow·Portal 이미지 빌드 | `make airflow-image`, `make portal-image`가 사내 ODBC artifact·미러로 빌드해 사내 이미지 저장소에 push | 로컬 Airflow 3 검증은 완료. 사내 의존성·ODBC·npm 미러 빌드와 push는 미확인 | [이미지 준비](../../../airflow/docs/02-artifacts.md), [Portal 설치](../../../portal/README.md#a-최초-설치) | 운영자 |
| Airflow 운영 입력 | 기존 Airflow 계정·client가 있으면 운영 env 일치 확인, 사내 CA 파일을 `deploy/shared/certs/ca/`에 배치(`airflow-oidc-ca` ConfigMap은 `airflow-up`이 생성) | 신규 설치값은 서버 env에 선언. 기존 계정·CA 등록 여부 미확인 | [Airflow 준비](../../../airflow/docs/01-prepare.md), [Airflow 배포](../../../airflow/docs/03-deploy.md) | 운영자 |
| Airflow 배포 | `https://airflow.etch.samsungds.net` 로그인 | 노드 Ready·배포 미확인 | [Airflow 배포](../../../airflow/docs/03-deploy.md) | 운영자 |
| Airflow DAG 공유 폴더 전환 | `khinfow01`의 공유 디렉터리를 스케줄러와 DAG Processor에 마운트 | 저장소 선언. 기존 DAG 백업·파일 이관·운영 재배포 및 목록 확인 필요 | [공유 폴더 전환](../../../airflow/docs/04-operations.md#공유-폴더-전환) | 운영자 |
| Monitoring 배포 | Grafana·Prometheus·Alertmanager 접속과 지표 수집 | 저장 폴더 준비는 사용자 확인. 배포·접속 미확인 | [Monitoring 설치](../../../monitoring/README.md) | 운영자 |
| Grafana SSO와 조회 권한 | Members 권한 두 개, Grafana 조직 분리, Prometheus·Alertmanager 공용 Ingress 제거 | 저장소 선언. 운영 적용과 조직별 SSO 접근 미확인 | [Monitoring 운영 안내](../../../monitoring/docs/02-operations.md#grafana-조직별-조회-권한) | 운영자 |
| Headlamp 배포 | `https://headlamp.etch.samsungds.net` 로그인 | 배치 노드·배포 미확인 | [Headlamp 설치](../../../headlamp/README.md) | 운영자 |
| IAM 웹 공개 | [IAM 공개 주소](services.md#서비스-접속-주소)에서 웹과 업무 부하 API 제공 | 주소 확정. 웹·API 이미지와 Kubernetes 정의는 저장소에 있음. 운영 Zot 게시, DNS·TLS·Ingress와 로그인 확인 필요 | [IAM 배포](../../../iam/README.md#c-배포-후-확인) | 미확인 |
| FTP 배포 | 대상 노드에 `etch.io/ftp-enabled=true` 라벨과 송수신 성공 | 대상 노드·배포 미확인 | [FTP 설치](../../../ftp/docs/01-install.md) | 운영자 |
| Portal Kubernetes 전환 | 테스트·운영 Portal을 Docker 서버에서 이 클러스터로 이전 | 이미지 빌드·push, 운영 Worker, 외부 DB, 업무 파일 PVC, 로그인 client 적용 미확인 | [Portal 접속 구분](services.md#portal-테스트운영-접속-구분), [서버가 받는 이미지](repositories.md#서버가-받는-이미지), [Portal 설치](../../../portal/README.md) | 미확인 |

## 4. 보안·운영 체계

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 관리자 비밀번호 교체 | 강한 값으로 교체하고 Git 밖에서 관리 | Git 추적 env에 값이 있음: `deploy/keycloak/env/prod.env`의 `bootstrap-admin-password`, `deploy/portal/env/prod/api.env`의 `DJANGO_SUPERUSER_PASSWORD`, `deploy/minio/env/prod.env`의 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`(기본값) | [환경설정](../configuration/environment.md), [Keycloak Secret 불일치](../../../keycloak/docs/03-operations.md#secret-불일치와-기존-db-복구) | 미확인 |
| 백업 체계 | 앱 데이터·Keycloak DB·etcd의 백업 위치·주기·복구 검증 | 미확정 | [운영 책임·백업](operations.md#운영-책임백업인증서) | 미확인 |
| 서버 checkout·Git | 사내 Git 주소·배포 브랜치·서버 checkout 경로 확정 | 미확인 | [사내 저장소 주소](repositories.md#공통-주소와-경로-규칙), [운영 파일 위치](operations.md#운영-파일과-데이터-위치) | 미확인 |
| 접속·담당자 | 노드 명령 실행·관리망 경유지·서비스 담당자 | 미확인 | [추가 확인](servers.md#추가-확인접속-정보) | 미확인 |
| 접근 경로 기록 | DNS·방화벽·LB·인증서 발급·노드 명령 실행·외부 DB의 접근 방법과 계정 위치를 처음 사용할 때 기록 | 모든 절 미확인 | [접근 경로](access.md) | 운영자 |
| 권한관리(IAM) Keycloak 설정 | 운영 공개 주소로 IAM client를 구성하고 조직 역할·권한·카탈로그를 적용. `iam-verify`로 확인 | 주소 확정. Keycloak 적용은 미확인 | [IAM 가이드](../../../iam/README.md) | 미확인 |
| 원소속 부서 프로필 | 운영 Keycloak에 `original_deptname`을 등록하고 IAM 사용자 패널에서 확인 | 저장소 선언. 운영 적용 미확인 | [Keycloak과 IAM 설정 확인](../operations/05-transition.md#6-keycloak과-iam-설정-확인) | 미확인 |
| 서버 상태 보고서 전달 | 운영 agent가 `make ops-report`로 만든 별칭 보고서를 외부 개발 환경에 전달하고, 그 결과로 이 문서의 `미확인` 행을 정리 | 미확인. 보고서 생성 도구는 서버에서 실행된 적 없음 | [서버 상태 보고](../operations/04-drift.md#서버-상태-보고), [별칭 표](aliases.json) | 사용자 |
