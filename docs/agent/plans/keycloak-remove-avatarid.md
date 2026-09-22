# ExecPlan: Keycloak 중복 avatarid 제거

## 목표
- Keycloak을 먼저 정비하고 EPID는 기본 username에만 저장한다.

## 현재 상태
- userid 속성 mapper가 avatarid를 중복 저장하며 epid-username mapper가 기본 username을 채운다.

## 범위
- Keycloak 프로필, mapper, 생성 YAML, 관련 테스트와 문서.
- Django DB와 프론트엔드는 후속 정비 대상으로 유지한다.

## 설계
- avatarid 프로필 정의와 IdP userid 속성 mapper를 제거한다.
- Portal userid 토큰은 기본 username property를 읽어 기존 claim 계약을 유지한다.
- 기존 사용자 속성값을 일괄 삭제하지 않는다. migration/env 변경은 없다.

## 실행 단계
- [x] 설정과 회귀 테스트 수정
- [x] YAML 생성 및 검증

## 검증
- bash -n deploy/k8s/keycloak/sync-oidc-claim-mappers.sh
- make k8s-export 및 make k8s-render
- node --test scripts/tests/environment.test.cjs scripts/tests/k8s-routing.test.cjs
- npm run agent:audit:docs 및 git diff --check

## 위험과 대응
- 기존 userid 토큰 mapper는 삭제하지 않고 property mapper로 갱신한다.
- 기존 계정은 사내 재로그인 후 username에 EPID가 반영된다.

## 진행 기록
- 2026-09-14: Keycloak 우선 정비 범위 확정.
- 2026-09-14: 지정한 검증 명령 모두 통과. mapper/환경/라우팅 테스트 33개 통과. 이번 변경의 실제 Keycloak 로그인 검증과 운영 배포는 수행하지 않았다.
- 외부 claim 이름과 값의 계약, 환경 변수는 유지하므로 로컬 dummy와 Compose 수정은 필요하지 않다.
