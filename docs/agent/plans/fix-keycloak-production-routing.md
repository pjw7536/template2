# ExecPlan: Keycloak 식별 속성 보호와 운영 라우팅 수정

## 목표
- 일반 사용자의 사번 등 사내 식별 속성 수정을 차단한다.
- TLS 종료 뒤에도 HTTPS 정보를 유지하고 Portal Ingress를 처리한다.
- claim mapper의 두 단계 적용과 재실행 절차를 명확히 한다.

## 현재 상태
- IdP mapper Job은 unmanagedAttributePolicy=ENABLED를 설정한다.
- Nginx는 전달된 프로토콜을 내부 HTTP로 덮어쓴다.
- 공유 Traefik은 etch-sso만 감시하며 Portal은 tailwind-internal에 있다.
- IdP mapper와 Portal token mapper는 각각 별도 Job에서 등록한다.

## 범위
- Keycloak mapper 스크립트, 공유 프록시, 운영 namespace RBAC, 관련 테스트와 문서 및 생성 YAML.
- 실제 사내 클러스터 적용과 Git 커밋은 포함하지 않는다.

## 설계
- 미정의 사내 속성은 관리자만 읽고 수정할 수 있는 ADMIN_EDIT 정책을 사용한다.
- Nginx는 Ingress가 전달한 http/https를 유지하고 헤더가 없으면 접속 프로토콜을 사용한다.
- Traefik 감시 대상에 Portal namespace를 추가하고 그 namespace에만 필요한 Role을 부여한다.
- public API와 DB schema는 변경하지 않는다. 기존 IdP/클라이언트 mapper 등록 분리를 유지한다.

## 실행 단계
- [x] 설정과 적용 문서 수정
- [x] mapper 정책과 렌더링 RBAC 회귀 테스트, Nginx 실제 전달 검증
- [x] 생성 YAML 갱신 및 검증 결과 기록

## 검증
- node --test scripts/tests/environment.test.cjs scripts/tests/k8s-routing.test.cjs: 24개 통과
- make k8s-render 및 make k8s-export
- Nginx 컨테이너에서 프록시를 거친 http/https 헤더 검증
- bash scripts/agent/check_compose_configs.sh 및 git diff --check

## 위험과 대응
- 기존 완료 Job은 자동 재실행되지 않는다. ConfigMap 갱신 후 Job 재실행을 문서화한다.
- Portal 권한 부여는 운영 overlay에 한정해 다른 namespace 접근을 확대하지 않는다.
- 실제 클러스터와 사내 OIDC 연결은 로컬 검증 결과와 구분한다.

## 진행 기록
- 2026-09-11: 사용자 수정 요청에 따라 계획 작성. 기존 작업 내용은 유지한다.
- 2026-09-11: ADMIN_EDIT 정책, 원래 프로토콜 전달, Portal namespace 감시와 RoleBinding을 반영했다. 렌더링 결과의 ServiceAccount namespace가 etch-sso로 유지됨을 검증했다.
- 2026-09-11: Nginx 컨테이너에서 API/callback/SSE/MinIO/Web의 HTTPS·HTTP·헤더 없는 요청 15건을 검증했다. Compose 설정 검사와 Kustomize 6개 렌더링이 통과했고 전달용 YAML을 갱신했다.
- 2026-09-11: 격리된 Keycloak 26.7.1에서 기존 ENABLED 정책의 사번 변경을 재현했다. 동일한 Account API 요청이 ADMIN_EDIT에서는 HTTP 204를 반환해도 사번을 변경하지 않음을 저장값으로 확인했다. 관리자 경로의 속성 저장은 유지된다. 실제 사내 서버에는 적용하지 않았다.
