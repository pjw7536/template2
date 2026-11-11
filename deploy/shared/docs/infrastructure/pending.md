# 서버 적용 대기 작업

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

저장소 선언·확정된 목표와 실제 사내 서버 상태가 아직 맞지 않아 **서버에서 수행해야 하는 작업**의 목록입니다.
값의 원본은 각 행의 원본 문서이며 이 문서에는 작업·현재 상태·절차만 둡니다. 기록 형식은 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.

- 작업을 서버에 적용하고 확인하면 원본 문서의 현재 값을 갱신하고 이 문서의 행을 삭제합니다. 완료 기록은 남기지 않습니다.
- 새 작업은 해당 분류에 행을 추가합니다. 주체가 정해지지 않았으면 `미확인`으로 둡니다.
- 상태의 `미확인`은 서버 조회·사용자 확인이 없다는 뜻이며 미적용으로 단정하지 않습니다. 작업 전 실제 상태를 조회합니다.

## 1. 네트워크·DNS·인증서

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 운영 SSO DNS 전환 | `sso.etch.samsungds.net` → APP VIP | 현재 DNS는 `etch-sso.samsungds.net` → `khplane01w09` 주소. 새 주소 등록 미확인 | [전환·계획 주소](network.md#전환계획-주소) | 사용자 |
| 앱별 DNS 등록 | 서비스 주소 표의 앱 도메인 → APP VIP | 미확인 | [서비스 접속 주소](services.md#서비스-접속-주소), [DNS 명명](network.md#dns-명명과-향후-구역-위임) | 사용자 |
| 업무 인증서 추가 신청·발급 | DNS SAN 92개·IP SAN 1개 | 신청안 작성. 제출·발급 미확인 | [업무 HTTPS 인증서](network.md#업무-https-인증서) | 미확인 |
| 공용 TLS 등록 | 발급 인증서를 공용 Traefik 저장소에 등록 | 미확인 | [인증서 적용](../certificates/apply.md) | 운영자 |
| FTP 방화벽 개방 | 허용 출발지 → FTP 노드 TCP `6380`, `8076–8079` | 미확인 | [FTP 직접 접속](network.md#ftp-직접-접속) | 미확인 |

## 2. 클러스터·공통 구성

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 공용 Traefik·APP VIP backend | backend 2대에서 Traefik이 443 응답 | 저장소 기본 배치는 `khplane01w09` 1대. 실제 배치·LB 응답 미확인 | [VIP와 backend](network.md#vip와-backend), [backend 확장](../ingress/expand.md) | 운영자 |
| 사내 미러 pull 확인 | 서버가 받는 모든 이미지·패키지를 대상 노드에서 받을 수 있음 | 미확인 | [서버가 받는 이미지](repositories.md#서버가-받는-이미지), [패키지 주소](repositories.md#패키지chartartifact-주소) | 운영자 |
| API server 버전 확인 | 실제 버전을 서버 현황에 반영 | CP1 확인값 `v1.36.0`, metrics-server 안내에는 1.36.4로 기록되어 충돌 | [설치 기준](servers.md#확인된-worker-설치-기준), [metrics-server](../kubernetes/control-plane.md#metrics-server-설치) | 운영자 |
| metrics-server 설치 | `kubectl top` 동작 | 미확인 | [metrics-server 설치](../kubernetes/control-plane.md#metrics-server-설치) | 운영자 |
| API server OIDC 인증 | Headlamp 사용자 토큰으로 Kubernetes API 인증 | 미확인 | [API server OIDC](../kubernetes/oidc.md) | 운영자 |

## 3. 앱 배포

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| Keycloak 배포·공개 주소 | `sso.etch.samsungds.net`에서 realm `etch` 로그인 | 저장소는 새 주소 선언. 서버 적용·접속 미확인 | [Keycloak 배포](../../../keycloak/README.md), [서비스 배치](services.md#앱별-배치와-스토리지-선언) | 운영자 |
| Portal client 재등록 | Portal client의 groups mapper 이름이 `sdwt-groups` | 기존에 Portal client를 등록했다면 서버에 이전 이름 `portal-sdwt-groups`가 남아 있음. 재등록 시 자동 교체 | [Portal client 등록](../../../portal/docs/01-install.md#keycloak-client-등록) | 운영자 |
| MinIO 재생성 | `/appdata/minio` 저장소로 새로 설치 | 데이터 없음은 사용자 확인. 재생성 완료 미확인 | [MinIO 설치](../../../minio/README.md), [서비스 배치](services.md#앱별-배치와-스토리지-선언) | 운영자 |
| Airflow 이미지 준비 | `airflow:3.3.2-release-1`을 CP1에서 사내 ODBC artifact 포함으로 빌드해 `khinfow01`에 반입 | 로컬 Airflow 3 검증은 완료. 사내 의존성·ODBC 빌드는 미확인 | [이미지 준비](../../../airflow/docs/02-artifacts.md) | 운영자 |
| Airflow 운영 입력 | 외부 env에 관리자 비밀번호·OIDC client secret 실제 값 입력, `airflow-oidc-ca` ConfigMap 생성 | 저장소 `deploy/airflow/env/k8s.env`는 `replace-here` 값이라 실제 값 검사에서 중단됨 | [Airflow 준비](../../../airflow/docs/01-prepare.md), [Airflow 배포](../../../airflow/docs/03-deploy.md) | 운영자 |
| Airflow 배포 | `https://airflow.etch.samsungds.net` 로그인 | 노드 Ready·배포 미확인 | [Airflow 배포](../../../airflow/docs/03-deploy.md) | 운영자 |
| Monitoring 배포 | Grafana·Prometheus·Alertmanager 접속과 지표 수집 | 저장 폴더 준비는 사용자 확인. 배포·접속 미확인 | [Monitoring 설치](../../../monitoring/README.md) | 운영자 |
| Headlamp 배포 | `https://headlamp.etch.samsungds.net` 로그인 | 배치 노드·배포 미확인 | [Headlamp 설치](../../../headlamp/README.md) | 운영자 |
| FTP 배포 | 대상 노드에 `etch.io/ftp-enabled=true` 라벨과 송수신 성공 | 대상 노드·배포 미확인 | [FTP 설치](../../../ftp/docs/01-install.md) | 운영자 |
| Portal Kubernetes 전환 | 테스트·운영 Portal을 Docker 서버에서 이 클러스터로 이전 | 이미지 registry·tag, 운영 Worker, 외부 DB, 업무 파일 PVC, 로그인 client 미확정 | [Portal 접속 구분](services.md#portal-테스트운영-접속-구분), [서버가 받는 이미지](repositories.md#서버가-받는-이미지), [Portal 설치](../../../portal/README.md) | 미확인 |

## 4. 보안·운영 체계

| 작업 | 목표 | 현재 상태 | 절차·원본 | 주체 |
| --- | --- | --- | --- | --- |
| 관리자 비밀번호 교체 | 강한 값으로 교체하고 Git 밖에서 관리 | Git 추적 env에 값이 있음: `deploy/keycloak/env/prod.env`의 `bootstrap-admin-password`, `deploy/portal/env/prod/api.env`의 `DJANGO_SUPERUSER_PASSWORD`, `deploy/minio/env/prod.env`의 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`(기본값) | [환경설정](../configuration/environment.md), [Keycloak Secret 불일치](../../../keycloak/docs/02-deploy.md) | 미확인 |
| 백업 체계 | 앱 데이터·Keycloak DB·etcd의 백업 위치·주기·복구 검증 | 미확정 | [운영 책임·백업](operations.md#운영-책임백업인증서) | 미확인 |
| 서버 checkout·Git | 사내 Git 주소·배포 브랜치·서버 checkout 경로 확정 | 미확인 | [사내 저장소 주소](repositories.md#공통-주소와-경로-규칙), [운영 파일 위치](operations.md#운영-파일과-데이터-위치) | 미확인 |
| 접속·담당자 | 노드 SSH·관리망 경유지·서비스 담당자 | 미확인 | [추가 확인](servers.md#추가-확인접속-정보) | 미확인 |
