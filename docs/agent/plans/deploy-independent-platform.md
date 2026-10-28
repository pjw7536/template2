# ExecPlan: deploy 독립 운영과 Portal 후속 배포

## 목표
- 기존 Kubernetes에서 deploy와 최소 루트 파일만으로 Portal 외 서비스를 먼저 운영한다.
- 기존 앱의 라우팅·VIP·데이터를 보존하면서 Portal을 나중에 연결한다.

## 현재 상태
- 서버 경계는 대체로 분리됐지만 checkout에 docs 전체가 포함되고 Portal 제외 그룹이 없다.
- 공용 Traefik 재적용이 Keycloak에 결합되고 shared/server-up이 Airflow 흐름을 소유한다.
- Portal 연결은 정적 패치 또는 수동 편집이며 서버 Secret 등록은 현재 context를 사용한다.
- 기존 staged 변경을 포함한 사용자 작업이 있으므로 index를 변경하지 않는다.

## 범위
- deploy 공통·앱별 실행 도구, 루트 Makefile, 관련 운영 문서와 local의 확정 잔재를 수정한다.
- apps의 제품 소스는 제외하며 apps/tooling의 관련 검사만 갱신한다.
- 실제 클러스터 적용, DB 변경, 커밋·push, ADFS 인증 제거, Helm 전면 공통화는 수행하지 않는다.

## 설계
- apps.json에 platform 그룹을 추가하고 공통 운영 문서는 deploy/shared/docs만 checkout한다.
- platform에서 Portal을 추가할 때 checkout all을 사용한다. 선택은 기존 범위 교체이며 ignored 파일 보호를 유지한다.
- ingress-check/up은 명시 context로 공용 리소스만 검사·적용하고 기존 감시·VIP·배치를 보존한다.
- ingress-connect APP=portal은 기존 Portal RBAC를 확인한 뒤 resourceVersion 검사와 함께 감시 인자만 수정한다.
- 공통 로딩·렌더 helper와 Airflow 업무 흐름을 분리하고 server-up CLI는 호환 wrapper로 유지한다.
- 서버 k8s-env는 명시 context를 요구한다. 로컬 호출·env 합성 순서·MinIO 전달 키는 유지한다.
- 미사용 인자 두 개와 상수 한 개를 제거하고 별도 MinIO 파서를 공통 env 파서로 교체한다.
- DB schema·제품 API·OIDC endpoint 변경은 없다.

## 실행 단계
- [x] platform checkout·카탈로그 기반 검사·서버 문서 경계를 정리한다.
- [x] 공통 helper·Airflow 책임을 분리하고 기존 CLI 호환성을 확인한다.
- [x] 공용 Ingress 검사·적용·Portal 연결 명령과 회귀 검사를 추가한다.
- [x] 명시적 Secret context·로컬 잔재·env 파서·과거 문서를 정리한다.
- [x] 관련 검사·렌더·문서 검증 후 결과와 실행 한계를 기록한다.

## 검증
- node --test apps/tooling/tests/server-checkout.test.cjs apps/tooling/tests/environment.test.cjs apps/tooling/tests/k8s-routing.test.cjs apps/tooling/tests/portal-deployment.test.cjs
- python3 -m unittest discover -s deploy/shared/tests
- python3 -m unittest discover -s deploy/airflow/tests
- python3 -m unittest discover -s deploy/headlamp/tests
- python3 -m unittest discover -s deploy/monitoring/tests
- python3 -m unittest discover -s apps/tooling/agent/tests -p test_local_k8s.py
- make k8s-render-local k8s-render-server
- make env-profile-key-check ENV_APP=portal ENV_PROFILE=local
- 변경한 문서의 저장소 검사와 git diff --check를 실행한다.
- 임시 checkout·가짜 kubectl로 실행 경계를 검증하며 실제 클러스터 적용과 구분한다.

### 실행 결과
- Node 배포·라우팅·env·checkout 회귀 검사 78개 통과.
- 공통 배포 단위 검사 68개, Headlamp 15개, Discovery 17개, 로컬 Kubernetes 9개 통과.
- Airflow 40개 검사 중 2개, Monitoring 8개 검사 중 1개는 기존 도구 조건으로 생략됐고 나머지는 통과.
- 로컬·서버 Kustomize 렌더, Portal 로컬 env 키 검사, 문서 색인 검사, 변경 Python 17개 구문 및 git diff --check 통과.
- 앱 구조 검사는 기존 root 소유의 빈 apps/web와 deploy/nginx/default.conf 디렉터리 때문에 실패했다. 일반 권한과 비대화형 sudo에서 삭제·이동 권한이 없어 경로를 그대로 보존했다. 해당 경로의 파일은 없으며 이번 변경으로 생성한 경로가 아니다.
- 실제 Kubernetes 적용·rollout·접속·로그인·FTP 송수신은 수행하지 않았다. 위 테스트의 클러스터 호출은 fixture로 대체했다.
- 초기 및 구현 후 Git index SHA-256은 9e7e31315c685cc6a45705c6cc75ba43cbb836b1eef6d4b6827f597271349c39로 동일했다.

## 위험과 대응
- 위험: 공용 Ingress 재적용으로 기존 namespace·VIP 배치가 축소될 수 있다.
- 대응: 현행 설정을 보존하며 Portal 연결은 controller 전체 apply 대신 낙관적 JSON Patch를 사용한다.
- 위험: checkout 범위 축소로 ignored 인증서·백업이 제거될 수 있다.
- 대응: 제외할 ignored 파일이 있으면 기존 보호 로직으로 중단하고 보존 후 재시도하도록 안내한다.
- 위험: Keycloak 입력 검사 실패 전에 공용 리소스를 적용할 수 있다.
- 대응: 검사와 적용을 분리하고 앱의 모든 사전 검사를 통과한 뒤 적용한다.

## 진행 기록
- 2026-10-28: 사용자 승인 계획과 제품 소스 제외·tooling 검사 예외를 기록했다. 초기 index SHA-256은 별도 확인했으며 구현 중 stage하지 않는다.
- 2026-10-28: platform 그룹과 docs 제외, 독립 Ingress 명령, Portal의 낙관적 연결 패치를 구현했다. 기존 Portal RBAC 이름은 유지하고 정적 패치를 제거했다.
- 2026-10-28: Airflow 소유 흐름과 공통 runtime을 분리했다. Keycloak은 Airflow를 로드하지 않으며 기존 server-up CLI는 유지한다.
- 2026-10-28: Headlamp도 공통 감시 패치 계산을 재사용한다. Ingress 재적용은 기존 namespace를 수정하지 않고, 새 namespace만 create한다.
- 2026-10-28: Secret 등록에 명시 context를 적용하고 Discovery가 선택 context를 자식 도구에도 강제하도록 보완했다. MinIO 합성과 미사용 항목을 정리했다.
- 2026-10-28: 승인 범위의 코드·문서 검증을 완료했다. 기존 빈 디렉터리의 OS 권한으로 인한 구조 검사 실패는 별도 기록하며 제품 소스·사용자 stage·실제 클러스터는 변경하지 않았다.
