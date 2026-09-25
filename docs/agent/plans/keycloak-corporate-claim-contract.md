# ExecPlan: Keycloak 사내 OIDC 공통 claim 계약

## 목표
- Keycloak을 먼저 정비해 사내 OIDC의 업무 claim 이름을 공통 저장·발급 기준으로 사용한다.
- 앱은 공용 Default Client Scope를 연결해 같은 계약을 받는다.

## 현재 상태
- 수신·발급 목록은 sync-oidc-claim-mappers.sh의 16개다.
- first_name, last_name, origincomp는 현재 mapper 삭제 대상이다. 19개 지원 여부는 사용자 답변 대기 중이다.
- 내부 별칭 loginid→knox_id, deptname→department, grdName→grd_name을 사용한다.
- Portal client 등록 시 dedicated mapper 16개를 생성한다.
- 사용자 EPID는 Keycloak 기본 username에 저장하고 사내 broker 연결은 유지한다.
- 로컬 Keycloak은 사내 IdP 없이 sabun과 표준 프로필로 로그인하는 최소 mock이다.

## 범위
- 이번 단계: Keycloak 프로필, IdP mapper, 공용 scope, Portal client 연결, 배포 안내와 테스트.
- Django 사용자 모델·권한 제거, frontend 변경, 실제 운영 DB 초기화는 이번 단계에 포함하지 않는다.
- 사용자 사전 등록·최초 broker 연결은 참조 테이블 계약과 계정 연결 정책을 별도 확정한 뒤 구현한다.

## 설계
- 내부 커스텀 이름은 사내 claim과 일치시킨다. 충돌하는 사람 이름 username만 display_name으로 저장한다. userid·mail·givenname·surname도 원본 속성에 보존하고 기본 username에는 로그인 식별용 EPID를 별도로 반영한다.
- corporate-profile-v1 공용 OIDC scope가 ID Token·Access Token·UserInfo에 기존 외부 이름을 발급한다.
- Keycloak 소유 작업이 공용 scope를 관리하며, Portal 소유 작업은 이 scope를 Default로 연결한다.
- 새 client의 기본 연결과 기존 client의 명시적 연결을 구분한다. Headlamp 그룹 mapper는 유지한다.
- source 이름·타입·누락값은 확인된 사내 계약을 따른다. 사내에 없는 값을 합성하지 않는다.
- 기존 사용자 ID와 broker 연결은 보존한다. 내부 별칭 전환은 기존 값 이관 또는 사내 재인증 절차를 함께 준비한다.
- 그룹·SDWT 권한은 별도 계약으로 유지하며 사내 프로필 scope에 섞지 않는다.

## 실행 단계
- [x] 현재 claim과 mapper·테스트 조사
- [ ] 사용자가 16개 유지 또는 19개 지원을 확정
- [ ] 공통 scope 및 내부 속성 표준화
- [ ] 기존 client mapper 전환과 사용자 속성 전환 절차
- [ ] 회귀 테스트·export·문서 갱신

## 검증
- Bash 구문 검사, JSON 파싱, mapper API 호출 회귀 테스트
- node --test apps/tooling/tests/environment.test.cjs
- make k8s-export
- make server-check APP=keycloak PROFILE=prod
- local 없는 배포 경계와 mock 로그인 계약 확인
- 실제 claim 비교·재로그인 검증은 운영 연결 가능 여부를 별도 보고한다.

## 위험과 대응
- 신규 프로필 적용 후 이전 속성만 남으면 일부 claim이 비어질 수 있다. 데이터 전환을 동반한다.
- 공용 scope 변경은 연결된 앱 모두에 영향을 준다. 외부 이름·타입을 고정하고 duplicate mapper를 제거한다.
- 현재 Django의 19개 키는 실제 사내 응답 19개를 입증하지 않는다. 목록 확정 전 발급 계약을 변경하지 않는다.

## 진행 기록
- 2026-09-24: 사용자가 Django보다 Keycloak을 먼저 완성하도록 요청했다. claim 목록 확인 질문을 제시했고 현재 구현을 조사했다.
- 2026-09-24: 사용자는 원본 속성 보존(사람 이름 username만 예외)을 확정했다. 소속 user_sdwt_prod·line_id 추가는 keycloak-affiliation-claims.md에서 먼저 구현한다.
