# ExecPlan: 로컬 Portal 실행 복구

## 목표
- 현재 워크트리의 Portal을 로컬 브라우저에서 로그인하여 확인한다.

## 현재 상태
- localhost:8080은 404를 반환한다.
- 로컬 PostgreSQL 컨테이너가 종료되어 Keycloak이 DB에 연결하지 못한다.
- 재시작 후 API 등 일부 Pod가 Unknown 상태다.

## 범위
- local 실행 도구와 런타임의 필요한 복구, Portal 이미지 갱신.
- 기존 사용자 변경과 영속 데이터를 보존한다.

## 설계
- 기존 kind 클러스터와 Compose DB를 재사용한다.
- 기존 실행 도구의 DB 연결 및 배포 절차를 이용한다.
- 현재 워크트리의 migration과 인증 설정을 확인하고 필요한 로컬 연동만 수정한다.

## 실행 단계
- [x] DB와 클러스터 의존 서비스 복구
- [x] 현재 Portal 이미지 반영 및 migration 적용
- [x] 로그인과 기본 API 확인

## 검증
- kubectl Pod 준비 상태 확인
- localhost:8080 HTTP 응답 및 Keycloak 로그인 확인
- 수정 영역에 맞는 설정 또는 도구 검사

## 위험과 대응
- 위험: 기존 DB 또는 realm에 현재 소스와 다른 설정이 남아 있을 수 있다.
- 대응: 데이터 삭제 없이 상태를 먼저 확인하고 필요한 변경만 적용한다.

## 진행 기록
- 2026-09-26: PostgreSQL 종료와 Keycloak 연결 실패를 확인했다.
- worker 컨테이너 재시작으로 WSL bind mount를 복구하고, PostgreSQL 컨테이너만 재생성하여 기존 볼륨을 재사용했다.
- Secret의 stringData 병합으로 폐기된 ADFS 키가 남는 문제를 재현했다. local/shared/scripts/k8s.py에서 기존 Secret의 data 전체를 JSON Patch로 교체하도록 수정하고 회귀 테스트를 추가했다.
- 기존 realm은 삭제하지 않고 최신 fixture의 역할·그룹·EPID 계정을 SKIP 방식으로 추가하고 Portal claim mapper를 갱신했다. 기존 dummy.user와 이메일이 겹치는 90000001에는 dummy.user+90000001@example.com을 사용했다. 변경 전 상태는 비공개 runtime 파일에 저장했다.
- 상태 출력과 smoke 로그인 계정을 90000001로 맞춘다. WSL 재시작 후 복구 절차를 local/README.md에 기록한다.
- 기존 dashboard DB의 EPID 없는 사용자 때문에 0008 migration이 실패했다. 현재 Portal README의 새 DB 계약에 따라 dashboard는 보존하고 dashboard_keycloak을 별도 생성한다. 로컬 기동은 합성된 API env의 DB 이름으로 없는 DB만 생성하도록 보완한다.
- Portal API/Web 이미지 빌드·반입, 새 DB migration 전체 적용과 seed, 서비스 rollout을 완료했다.
- 검증 통과: Secret 회귀 테스트 2개, local-deployment Node 테스트 2개, k8s-render-local, env-profile-key-check portal/local, check-api, makemigrations-check.
- localhost:8080 HTML 200과 API health 정상 응답을 확인했다. EPID 계정 5개의 실제 Keycloak code 로그인과 메일/assistant/admin 권한을 모두 확인했다.
- Keycloak 복구에는 [공식 Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html)를 사용했다. 전체 앱 smoke는 이번 Portal 복구 검증 범위에 포함하지 않았다.
