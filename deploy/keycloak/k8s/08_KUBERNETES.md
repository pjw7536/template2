# 08. Keycloak Kubernetes 원본 참고

[전체 설치 순서](../README.md)

처음 설치할 때 manifest를 개별 적용할 필요는 없습니다.
[서버 설치](../01_SERVER_SETUP.md)와 [Keycloak 설정](../04_SETUP_FLOW.md)의 Make 명령이 아래 원본을 사용합니다.

## 원본과 역할

| 원본 | 역할 |
| --- | --- |
| `kustomization.yaml` | 서버·공용 ingress·관리 ConfigMap 구성 |
| `server/stack.yaml` | PostgreSQL·Keycloak·PV/PVC·Service |
| `server/etch-realm.json` | 최초 `etch` realm 정의 |
| `oidc/setup-realm.sh` | realm 준비 |
| `oidc/setup-oidc.sh` | 사내 IdP 연결 등록 |
| `oidc/oidc-setup-job.yaml` | IdP Job 원본, Realm Job에도 재사용 |
| `claims/account-user-profile.json` | 사용자 필드·조회/편집 권한 |
| `claims/sync-oidc-claim-mappers.sh` | 수신·발급 mapper 등록 |
| `claims/claim-mappers-job.yaml` | 프로필·mapper Job 원본 |
| `claims/sdwt-access-scope.json` | 앱 연결 시 사용하는 SDWT groups scope |

Traefik은 `deploy/shared/ingress`에서 참조합니다.
서버 배포는 관리 ConfigMap을 준비하지만 Realm·IdP·프로필·mapper 설정 Job을 실행하지 않습니다.
각 Job의 이름은 [설정 결과 확인](../04_SETUP_FLOW.md#job-결과-확인)에 있습니다.

## 도구의 실행 범위

`setup_discovery.py`가 명시한 context로 ConfigMap과 선택 단계의 Job을 준비합니다.
프로필 단계는 `KEYCLOAK_PROFILE_ONLY=true`, 수신 mapper 단계는 `KEYCLOAK_SKIP_PROFILE=true`로 구분합니다.
사내 접속 정보는 실행 호스트에서 Discovery를 조회한 뒤 Secret으로 전달합니다.

Portal client Job은 `deploy/portal/k8s/jobs/keycloak-client`가 소유합니다.
SDWT 초기 등록은 Job 대신 관리자 API를 사용합니다.

## 렌더 파일

`rendered/`는 생성된 전달용 YAML이며 직접 편집하지 않습니다.
최초 설치 안내는 Python·Make를 사용하는 단계별 경로로 통일합니다.
전달용 YAML은 별도 배포 형태이므로 단계별 명령과 함께 적용하지 않습니다.
특히 전달 스택은 Headlamp namespace 감시·RBAC 등 별도 전제가 있어 최초 설치 명령을 대체하지 않습니다.

## 관리 도구의 참조 관계

| 도구 | 호출 경로·역할 |
| --- | --- |
| `scripts/up.py` | `keycloak-check/up`의 서버 배포 구현 |
| `scripts/setup_discovery.py` | 단계별 실행 파일과 공통 env 도구의 Discovery 해석 |
| `scripts/00`~`05` 실행 파일 | Make 명령이 호출하는 단계별 진입점 |
| `scripts/init_sdwt.py` | SDWT 그룹·사용자 등록과 앱 scope 연결 |
| `scripts/render.sh` | `k8s-export`가 사용하는 전달 YAML 생성기 |
| `scripts/migrate_claim_attributes.py` | 별도 `keycloak-claim-attributes-migrate` 진입점. 최초 설치에는 사용하지 않음 |

통합 `keycloak-oidc-check/setup`과 전달용 `export/`는 기존 운영 절차에서 참조하므로 유지합니다.
최초 설치는 [설정 안내](../04_SETUP_FLOW.md)의 단계별 명령만 사용합니다.
claim Job은 ConfigMap의 최신 스크립트를 직접 실행하며 임시 사본·realm 옵션 치환을 사용하지 않습니다.
