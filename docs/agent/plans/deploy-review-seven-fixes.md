# ExecPlan: deploy 코드 리뷰 7건 수정

## 목표
- 리뷰에서 재현한 7건을 모두 해결하고 각 실행 조건을 회귀 검사로 보장한다.
- 제품 소스와 기존 stage 상태를 보존하고 서버 적용 없이 구현을 검증한다.

## 현재 상태
- Portal probe는 localhost를 사용하지만 운영 env 검사에서 허용 호스트 포함을 확인하지 않는다.
- Keycloak 외부 env 입력은 profile 검증과 명시 context 요구를 우회할 수 있다.
- Airflow는 이전 Traefik snapshot을 적용하며 triggerer를 항상 재시작한다.
- Ingress 검사는 계산한 VIP 배치와 실제 보존할 배치를 혼동하고 정상 Worker pool도 거부한다.
- Keycloak은 공통 Ingress가 허용한 배치를 별도의 기본 selector 검사로 거부한다.

## 범위
- deploy 공통·앱별 도구와 관련 배포 문서·회귀 검사만 수정한다.
- 앱 제품 소스, 기존 credential, 실제 클러스터, Git index와 커밋은 변경하지 않는다.
- 앞선 격리 작업과 사용자 staged 변경을 그대로 보존한다.

## 설계
- Portal 운영 입력은 고정 probe Host인 localhost를 허용해야 하며 누락 시 적용 전에 실패한다.
- Secret 적용의 앱/profile 조합을 외부 env 경로 유무와 무관하게 검증하고 서버 context를 요구한다.
- Airflow 단독 배포는 resourceVersion을 검사하는 namespace 전용 패치를 사용한다. 선택 workload의 재시작 대상은 최종 렌더에서 결정한다.
- 공통 순수 함수에서 현재 감시·배치 보존과 최종 노드 선택 검사를 수행하고 Ingress와 Keycloak이 함께 사용한다.
- VIP 생략 시 보존한 배치가 각 Backend를 수용하는지 확인한다. 명시 VIP 변경은 기존 보호 규칙으로 배치를 계산한다.
- 명시 VIP의 필수 nodeAffinity는 노드별 단일 metadata.name 조건을 OR로 구성해 Kubernetes API의 field selector 검증을 만족시킨다.
- 일반 Worker pool은 스케줄 가능한 후보와 포트·replica 용량으로 검사하고, 선택되지 않을 비정상 노드 때문에 전체를 거부하지 않는다.
- DB·인증 endpoint·제품 API는 변경하지 않는다.

## 실행 단계
- [x] Portal probe 입력과 Secret profile/context 우회를 차단한다.
- [x] 공용 배치 보존·검증을 통합하고 VIP·Worker pool 재현을 회귀 검사로 추가한다.
- [x] Keycloak에 공용 배치 처리를 적용하고 실패 전 무변경 계약을 확인한다.
- [x] Airflow 동시 라우팅 보존과 선택 workload 재시작을 수정한다.
- [x] 관련 단위·배포 회귀·렌더·env·문서·구문·공백 검사를 실행한다.

## 검증
- node --test apps/tooling/tests/environment.test.cjs apps/tooling/tests/server-checkout.test.cjs apps/tooling/tests/k8s-routing.test.cjs apps/tooling/tests/portal-deployment.test.cjs
- python3 -m unittest discover -s deploy/shared/tests
- python3 -m unittest discover -s deploy/airflow/tests
- python3 -m unittest discover -s deploy/headlamp/tests
- python3 -m unittest discover -s deploy/monitoring/tests
- python3 -m unittest discover -s apps/tooling/tests -p test_keycloak_discovery.py
- make k8s-render-local k8s-render-server
- make env-profile-key-check ENV_APP=portal ENV_PROFILE=local
- make audit-docs, git diff --check, 수정 Python·셸 구문 검사
- fixture·고정 chart 렌더로 검증하며 실제 클러스터 성공과 구별한다.

### 실행 결과
- 배포·라우팅·env·checkout Node 회귀 검사 80개 통과(환경·checkout 75개, 라우팅·Portal 5개).
- 공통 배포 79개, Airflow 43개, Headlamp 15개, Monitoring 8개, Discovery 17개, 로컬 Kubernetes 9개 통과. 전체 251개 검사이며 중복 실행은 합계에서 제외했다.
- 고정 chart 검사는 기존 .tools/bin/helm을 PATH에 추가해 실행했고 Airflow·Monitoring의 도구 부재 생략 없이 통과했다.
- 로컬·서버 Kustomize 렌더, Portal 로컬 env 키, 문서 색인, 변경 Python 19개 구문, 셸 2개 구문, git diff --check 통과.
- 운영 API env의 probe 호스트 허용 여부는 값 출력 없이 확인했고 현재 파일은 조건을 만족한다. credential과 실제 env는 수정하지 않았다.
- 실제 클러스터 apply·rollout·접속·로그인은 수행하지 않았다. 동시 변경과 배치 검사는 fixture로, chart 구조는 고정 Helm 렌더로 검증했다.
- Git index는 시작 시 SHA-256과 동일하며 stage·commit·push하지 않았다.

## 위험과 대응
- 위험: 공통 배치 변경으로 기존 namespace·VIP·operator 배치를 덮어쓸 수 있다.
- 대응: 현행 배치를 합성한 뒤 실제 결과를 검증하고 입력 오류나 충돌 시 적용 전에 중단한다.
- 위험: 강화한 Portal 입력 검사가 기존 운영 env를 거부할 수 있다.
- 대응: localhost 허용 요구와 조치 방법을 문서화하고 기존 credential은 수정하지 않는다.
- 위험: 새 배치 검증을 Kubernetes 전체 스케줄러와 혼동할 수 있다.
- 대응: 정적 노드 선택·가용성·포트·용량을 검사하고 실제 rollout·접속 검증의 범위를 문서에 구분한다.

## 진행 기록
- 2026-10-28: 사용자 요청으로 리뷰 7건 모두 수정하기로 했다. 초기 index SHA-256은 9e7e31315c685cc6a45705c6cc75ba43cbb836b1eef6d4b6827f597271349c39다.
- 2026-10-28: VIP 복구 경로를 검증하면서 기존 matchFields In에 여러 노드를 넣는 형식이 API에서 거부됨을 확인했다. 리뷰 4번의 유효한 명시 배치 생성 범위에 포함해 노드별 OR 조건으로 수정한다. 근거는 [Kubernetes ValidateNodeFieldSelectorRequirement](https://github.com/kubernetes/kubernetes/blob/master/pkg/apis/core/validation/validation.go)의 In·NotIn 값 한 개 제한이다.
- 2026-10-28: Portal probe 호스트 요구와 Secret 앱/profile 조합을 사전에 검증하고 관련 운영 안내를 보완했다.
- 2026-10-28: 공용 plan_controller에서 현행 배치·label·annotation·감시를 보존하고 실제 후보 용량과 VIP Backend 수용 범위를 확인한다. Ingress와 Keycloak이 같은 함수를 사용한다.
- 2026-10-28: Keycloak의 전용 앱 Worker·Secret·TLS 검사와 실패 전 무변경 계약은 유지하면서 정상 Ingress pool을 허용했다.
- 2026-10-28: Airflow 단독 배포는 적용 직전 최신 controller를 조회해 감시 인자만 낙관적 패치한다. 호환 통합 경로도 resourceVersion을 유지한다.
- 2026-10-28: Airflow 재시작 대상은 최종 Helm 리소스에서 추출하며 triggerer 비활성화와 StatefulSet 선택도 검증했다.
- 2026-10-28: 리뷰 7건과 VIP API 형식 보완을 완료하고 251개 검사·렌더·env·문서·구문 결과를 기록했다.
