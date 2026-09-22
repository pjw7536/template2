# ExecPlan: Keycloak 단독 배포 라우팅 복원

## 목표
- 정상 동작하던 Keycloak 단독 HTTPS 구성을 유지하고 Portal 감시 확장을 별도로 적용한다.

## 현재 상태
- 사용자는 이전 단일 YAML 적용 시 정상, 현재 YAML 적용 후 HTTPS 오류를 보고했다.
- 현재 스택은 Portal namespace까지 감시하지만 해당 권한은 Portal overlay에 있다.
- Ingress에 websecure/TLS annotation도 추가돼 있다. 실제 장애 원인은 운영 로그 미확인이다.

## 범위
- Keycloak Traefik·Ingress 원본, 생성 YAML, Portal 선택 패치, 관련 문서와 라우팅 테스트.
- 인증 코드, Secret 값, DB와 기존 사용자 변경은 제외한다.

## 설계
- 단독 스택은 etch-sso만 감시하고 기존 Ingress TLS Secret 참조를 유지한다. 사용자 후속 지시에 따라 websecure/TLS annotation을 명시한다.
- Portal 배포로 RBAC를 준비한 후 JSON Patch로 감시 범위만 확장한다.
- 패치는 기존 인자를 검사해 예상하지 않은 구성을 덮어쓰지 않는다.

## 실행 단계
- [x] 원본 복원 및 선택 패치·문서 반영
- [x] 생성 YAML 갱신 및 회귀 검증

## 검증
- make k8s-export, make k8s-render
- node --test scripts/tests/k8s-routing.test.cjs
- npm run agent:audit:docs
- git diff --check

## 위험과 대응
- Traefik 설정 적용 시 재기동으로 잠시 접속이 끊길 수 있다.
- 운영 HTTPS 복구는 실제 서버 재적용과 브라우저 확인이 필요하며 로컬 검증으로 확정하지 않는다.
- 단독 스택 재적용은 Portal 감시를 해제하므로 Portal 운영 시 선택 패치도 다시 적용한다.

## 진행 기록
- 2026-09-14: 사용자 승인 범위에 맞춰 라우팅 복원과 선택 패치 분리를 시작했다.
- 2026-09-14: export와 6개 Kustomize 진입점 렌더링 통과. 라우팅 테스트 3개(단독 구성, kubectl 로컬 패치와 RBAC, 격리 Nginx 실제 전달) 통과. 문서 감사와 diff 공백 검사 통과. 운영 클러스터에는 적용하지 않았다.

- 2026-09-14: 사용자 후속 지시로 Ingress의 websecure/TLS annotation을 복원하고 테스트·안내를 동기화했다.
