# ExecPlan: 사내 Keycloak·PostgreSQL 스택

## 목표
- 사내 Kubernetes worker `khplane01w09`(`10.172.40.87`)에서 Keycloak과 전용 PostgreSQL을 함께 운영한다.
- StorageClass가 없는 현재 클러스터에서 worker 로컬 경로 `/appdata/keycloak-postgres`를 50Gi 정적 PersistentVolume으로 사용한다.
- Keycloak 공개 주소는 `https://etch-sso.samsungds.net`로 고정한다.
- 기존 Portal의 Keycloak code+PKCE 로그인 계약을 유지하면서 cluster 내부 token/JWKS 연결을 제공한다.
- 사내 OIDC의 19개 사용자 claim을 Keycloak 사용자 속성과 Portal token claim으로 일괄 동기화한다.

## 현재 상태
- `deploy/k8s/portal/overlays/local`에는 개발용 `start-dev` Keycloak과 Traefik이 있다.
- `deploy/k8s/portal/overlays/internal`은 외부 Keycloak을 전제로 하며 운영 Keycloak 리소스가 없다.
- 사내 클러스터에는 StorageClass와 IngressClass가 없다.
- 사내 registry mirror에서 Keycloak 26.7.1, PostgreSQL 16, Traefik 이미지를 받을 수 있다.

## 범위
- 추가: 운영용 Keycloak Deployment/Service/Ingress와 초기 `etch` realm.
- 추가: PostgreSQL StatefulSet/Service와 50Gi 정적 local PV/PVC.
- 추가: 전용 `etch-sso` namespace와 worker에 맞춘 Traefik Ingress Controller.
- 수정: internal Kustomize resource 목록과 사내 배포 문서.
- 추가: 기존 `oidc` Identity Provider와 `portal` client를 대상으로 하는 mapper 동기화 Job.
- 유지: 로컬 kind/Compose OIDC 설정, Django Auth 코드와 public API.
- 제외: 실제 credential/TLS 인증서 생성, DNS 등록, 사내 클러스터에 대한 실제 `kubectl apply`, DB HA와 자동 원격 백업.

## 설계
- Keycloak, PostgreSQL, Traefik은 `kubernetes.io/hostname=khplane01w09`에 고정한다.
- PostgreSQL 데이터는 `/appdata/keycloak-postgres` 정적 local PV에 보관하고 reclaim policy는 `Retain`으로 둔다.
- Keycloak은 production `start` 모드, PostgreSQL DB, 고정 public hostname, `xforwarded` proxy header와 management health endpoint를 사용한다.
- Traefik은 worker의 host port 80/443을 사용해 별도 LoadBalancer나 NodePort 없이 단일 worker의 Ingress를 제공한다.
- 초기 realm의 client secret과 Portal 공개 URL은 Kubernetes Secret 환경변수를 realm import placeholder로 주입한다.
- 브라우저 URL과 issuer는 공개 HTTPS DNS를, API token/JWKS 호출은 `http://keycloak.etch-sso.svc.cluster.local:8080` ClusterIP를 사용한다.
- mapper Job은 Keycloak Admin CLI를 사용해 기존 OIDC 연결값을 건드리지 않고 19개 Identity Provider mapper와 19개 client protocol mapper를 이름 기준으로 생성 또는 갱신한다.
- 사내 claim은 모두 문자열 단일값으로 저장하며 Identity Provider mapper는 `FORCE`, client mapper는 ID Token, Access Token과 UserInfo 출력을 활성화한다.
- Keycloak 26의 user profile 정책이 미정의 속성을 버리지 않도록 Realm의 unmanaged attribute policy를 `ENABLED`로 맞춘다.

## 실행 단계
- [x] internal Keycloak/PostgreSQL/Traefik manifest와 realm 설정을 추가한다.
- [x] internal Kustomize에 신규 리소스와 registry mirror image를 연결한다.
- [x] node/storage/DNS/TLS/Secret 준비와 배포 순서를 문서화한다.
- [x] Kustomize render, YAML 기본 검사와 문서 회귀 검사를 실행한다.
- [x] claim mapper 동기화 스크립트와 Kubernetes Job을 추가한다.
- [x] 단일 배포 YAML과 운영 적용·재실행 절차를 갱신한다.
- [x] 스크립트 문법, mock 기반 create/update 동작과 Kustomize render를 검증한다.

## 검증
- `make k8s-render`
- `git diff --check`
- `npm run agent:audit:docs`
- 렌더 결과에서 worker affinity, 50Gi local PV, mirror image, production Keycloak args와 Secret 참조를 확인한다.
- 실제 클러스터 검증은 control-plane에서 Secret/TLS/DNS 준비 후 rollout과 OIDC smoke test로 수행한다.

## 위험과 대응
- 위험: local PV가 worker 장애에 종속되고 디스크 장애 시 DB가 손실된다.
- 대응: `Retain`과 node affinity를 고정하고 운영 전 외부 백업 절차를 별도로 준비한다.
- 위험: `/appdata/keycloak-postgres`가 없거나 권한이 맞지 않으면 PVC/Pod가 기동하지 않는다.
- 대응: 배포 전에 node 관리 경로로 디렉터리와 50Gi 여유 공간을 확인한다.
- 위험: host port 80/443이 이미 사용 중이면 Traefik이 배치되지 않는다.
- 대응: 배포 전 node 포트 점유를 확인하고 Traefik rollout/event를 검증한다.
- 위험: DNS, TLS, Portal 공개 URL이 일치하지 않으면 OIDC issuer/callback이 실패한다.
- 대응: placeholder가 남은 상태에서는 배포하지 않고 동일한 공개 URL을 Secret, Ingress, Portal API 설정에 적용한다.
- 위험: mapper Job이 기존에 검증된 사내 OIDC endpoint와 client credential을 덮어쓸 수 있다.
- 대응: Job은 alias `oidc`의 존재만 확인하고 Identity Provider 연결 설정은 변경하지 않는다.
- 위험: 이미 로그인한 사용자는 신규 mapper 추가 직후 기존 세션에서 새 속성을 받지 못한다.
- 대응: mapper는 `FORCE`로 설정하고 사용자가 완전히 로그아웃한 뒤 다시 로그인하도록 문서화한다.
- 위험: unmanaged attribute 정책 `ENABLED`는 사용자 프로필에서 예상하지 않은 속성을 허용할 수 있다.
- 대응: 동기화 대상과 token 출력은 명시된 19개 claim으로 제한하고, 향후 보안 강화 시 managed user profile schema로 전환한다.

## 진행 기록
- 2026-09-08: 사용자 결정으로 worker `khplane01w09`, local PV 50Gi, 단일 replica, 사내 mirror 기반 구성을 확정했다.
- 2026-09-08: StorageClass/IngressClass 부재에 따라 정적 local PV와 저장소 기존 Traefik 패턴을 사용하기로 했다.
- 2026-09-08: 운영 manifest, Secret 기반 realm import, standalone 배포 절차와 Portal 연결값을 추가했다.
- 2026-09-08: local/internal Kustomize render, realm JSON parse, whitespace 검사와 문서 감사를 통과했다. 실제 API schema dry-run은 이 작업 환경에 kubeconfig가 없어 control-plane 검증 항목으로 남겼다.
- 2026-09-08: 사용자 결정에 따라 Keycloak 공개 DNS를 `etch-sso.samsungds.net`로 확정했다.
- 2026-09-08: 여러 ETCH 앱이 공유하도록 Realm을 `etch`, 사내 OIDC Identity Provider alias를 `oidc`로 단순화했다.
- 2026-09-09: control-plane 전달용 credential-free 단일 파일 `deploy/k8s/rendered/internal-keycloak-stack.yaml`을 생성했다.
- 2026-09-09: Keycloak 스택을 Portal과 분리한 전용 `etch-sso` namespace로 변경하고 내부 Service FQDN과 RBAC 참조를 맞췄다.
- 2026-09-10: 사용자가 사내 OIDC의 19개 claim이 백엔드 계약과 동일함을 확인하고, 사용자 속성 저장과 ID Token·Access Token·UserInfo 출력을 Kubernetes Job으로 자동화하기로 결정했다.
- 2026-09-10: 기존 `oidc` 연결을 보존하는 mapper 동기화 Job을 추가하고 create/update mock 검증, Bash 문법 검사, 19개 리소스 Kustomize render와 문서 감사를 통과했다.
- 2026-09-11: 서비스별 배포 구조로 이동했다. 현재 서버 진입점은 `deploy/k8s/keycloak`이며 claim 등록 Job은 별도 YAML로 적용한다. 후속 검증은 `k8s-service-layout.md`에 기록했다.
