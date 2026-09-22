# ExecPlan: 로컬 Kubernetes·Keycloak 전환

## 목표
- 로컬 PC의 kind에서 Portal 핵심 앱을 Kubernetes로 실행한다.
- Django API는 Kubernetes 밖의 로컬 PostgreSQL을 사용해 향후 사내 외부 DB 연결 계약을 미리 검증한다.
- 기존 Keycloak 브랜치에서 로그인에 필요한 authorization code, PKCE, JWKS 검증만 현재 `main`에 맞게 이식한다.
- 사내 클러스터가 준비되면 이미지 registry, DB, Keycloak, 도메인과 storage 설정만 internal overlay에서 교체할 수 있게 한다.

## 현재 상태
- 현재 작업 브랜치는 `feat/k8s-keycloak-local`이며 기준은 `main`의 `eb880ab7`이다.
- 저장소 로컬 도구 경로에 kind v0.32.0을 설치했으며 `kubectl apply -k`로 overlay를 렌더링한다.
- 기존 ADFS/dummy IdP의 `form_post` 흐름은 유지하고 `OIDC_PROVIDER=keycloak`일 때 code+PKCE 흐름을 사용한다.
- `feat/keycloak-auth-migration`과 `feat/keycloak-work-hub-squashed`에는 Keycloak code flow와 권한 원천 전환, Work Hub 변경이 함께 있다.
- 사용자 결정에 따라 Keycloak 권한 원천 전환, Account schema migration, Work Hub는 이번 범위에서 제외한다.
- kind의 Portal 핵심 앱은 Kubernetes 밖의 별도 PostgreSQL에 연결되며 migration Job과 실제 Keycloak 로그인을 통과했다.
- 사내 registry, DB, Keycloak, DNS, IngressClass, StorageClass 입력을 위한 internal overlay template을 추가했다.

## 범위
- 수정: Django Auth의 provider별 OIDC flow, Keycloak 로그인 테스트, callback URL과 env 설정.
- 추가: login 전용 local Keycloak realm, kind cluster 설정, Kustomize base/local/internal overlay, 외부 로컬 PostgreSQL Compose, 배포/검증 스크립트, local Headlamp 조회 UI.
- 수정: Makefile과 Kubernetes 전환·운영 문서.
- 유지: 기존 Compose dev dummy ADFS 로그인, 기존 Portal 권한 모델과 public API 응답.
- 제외: Keycloak을 권한 원천으로 사용하는 Account migration, Work Hub/Grist, Airflow·FTP·모니터링의 Kubernetes 전환, 운영 credential 생성, 실제 사내 서버 배포.

## 설계
- Auth는 `OIDC_PROVIDER=adfs|keycloak`로 flow를 선택한다. 기본값은 기존 `adfs`로 두어 Compose/offsite 동작을 보존한다.
- Keycloak은 authorization code + PKCE를 사용하고 API가 내부 token/JWKS endpoint를 호출한다. issuer와 browser authorize/logout URL은 공개 URL을 사용한다.
- Keycloak id_token은 issuer, audience, signature, exp, iat, nonce를 검증한 후 기존 Account identity upsert pipeline에 전달한다.
- 로컬 Keycloak은 kind 내부에서 개발 realm과 사용자만 제공하며 Portal 권한 원천이 되지 않는다.
- Django와 Keycloak client secret은 Kubernetes Secret으로 주입하며 실제 사내 비밀값은 저장소에 기록하지 않는다.
- 로컬 PostgreSQL은 Docker Compose로 kind 밖에서 실행하고 Kubernetes Service/EndpointSlice가 Docker host gateway를 가리킨다.
- Kustomize `base`는 API, Web, edge Nginx, MinIO와 공통 Service/PVC를 소유한다. `overlays/local`은 kind, local Keycloak, Ingress와 local image를, `overlays/internal`은 사내 입력용 template을 소유한다.
- Django migration은 API 기동과 분리한 Kubernetes Job으로 명시적으로 실행한다.
- local image는 kind에 직접 load하고 internal image는 registry tag로 교체한다.

## 실행 단계
- [x] 기존 Keycloak 브랜치의 login-only contract를 현재 Auth 구조에 맞게 이식한다.
- [x] legacy ADFS와 Keycloak flow의 단위/HTTP 계약 테스트를 추가한다.
- [x] 외부 로컬 PostgreSQL Compose와 연결용 Service/EndpointSlice 생성을 추가한다.
- [x] kind cluster, Kustomize base/local/internal overlay와 migration Job을 추가한다.
- [x] local Keycloak realm, API/Web/MinIO Secret 생성과 배포 스크립트를 추가한다.
- [x] Makefile 진입점과 configuration/operations 문서를 갱신한다.
- [x] Compose와 Kubernetes render, backend test, kind smoke test를 실행한다.
- [x] local Headlamp 조회 UI와 제한된 RBAC, port-forward 진입점을 추가하고 검증한다.

## 검증
- `git diff --check`
- `docker compose -f docker-compose.dev.yml config --quiet`
- `docker compose -f compose/k8s-local-db.yml config --quiet`
- `kubectl kustomize deploy/k8s/portal/overlays/local`
- `kubectl kustomize deploy/k8s/portal/overlays/internal`
- Docker Compose `api` 컨테이너에서 Auth 관련 Django 테스트
- `npm run agent:audit:api-boundary`
- kind cluster 생성 후 migration Job 완료, Deployment rollout, Keycloak discovery, Portal/API health smoke 확인

## 위험과 대응
- 위험: 기존 ADFS 로그인 회귀.
- 대응: provider 기본값을 `adfs`로 유지하고 기존 form_post 테스트와 Keycloak code flow 테스트를 함께 실행한다.
- 위험: 공개 issuer와 cluster 내부 Keycloak URL 불일치.
- 대응: public authorize/issuer와 internal token/JWKS URL을 분리하고 issuer claim은 public URL로 검증한다.
- 위험: 브랜치의 권한 원천 전환 코드가 함께 유입됨.
- 대응: Account model/migration/Admin API 코드는 이식하지 않고 login-only 파일과 테스트만 작성한다.
- 위험: kind Pod에서 호스트 PostgreSQL에 접근하지 못함.
- 대응: kind Docker network gateway를 EndpointSlice로 생성하고 migration 전에 TCP/DB 준비 상태를 확인한다.
- 위험: 사내 IngressClass, StorageClass, registry가 아직 미정.
- 대응: internal overlay에 명시적 교체 지점을 두고 실제 값은 서버 발급 후 확정한다.

## 진행 기록
- 2026-08-29: 사용자 결정으로 Keycloak 로그인만 우선 도입하고 기존 Portal 권한, Work Hub, Airflow/FTP/모니터링 전환은 제외했다.
- 2026-08-29: 브랜치 전체 merge 대신 Keycloak code+PKCE/JWKS 계약을 현재 `main`에 선택적으로 이식하기로 했다.
- 2026-08-29: local/internal Kustomize overlay, kind 자동화, 외부 PostgreSQL, local Keycloak과 운영 문서를 구현했다.
- 2026-08-29: Auth 41개 테스트, env/Compose/Kustomize render, backend/docs audit와 Django schema 검사를 통과했다.
- 2026-08-29: `make k8s-up` 재실행, migration/MinIO Job, 전체 Deployment rollout, Portal/API health와 Keycloak 실제 로그인을 검증했다.
- 2026-08-29: Headlamp v0.44.0, 조회 전용 RBAC와 `make k8s-ui` port-forward를 추가하고 UI·token proxy·Secret/write 차단을 검증했다.
