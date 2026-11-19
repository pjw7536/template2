# ExecPlan: Keycloak 기준 권한 통합 관리(IAM)

## 목표

- Keycloak이 모든 앱의 소속·권한 원본이다. 각 앱은 토큰 claim만 읽는다.
- 권한관리 웹(`apps/iam/web`)에서 팀·라인·SDWT 목록, 사용자 소속, 소속별 역할, 앱 역할을 관리한다.
- 앱 권한은 업계 표준 RBAC(앱 client 역할 + 그룹)로 두고, 역할 정의는 카탈로그 파일로 코드화한다.

## 확정 조건

| 항목 | 결정 |
| --- | --- |
| 웹 구조 | React 정적 웹. 백엔드·DB·service account 없음. 로그인한 관리자 토큰으로 Keycloak Admin API 직접 호출 |
| 사용자 | 플랫폼 관리자(`/iam/platform-admins`)만. 라인·SDWT 관리자 위임은 후속 |
| 변경 기록 | Keycloak 관리 이벤트(실제 관리자 이름으로 기록) |
| 업로드 | 팀·라인·SDWT 목록 CSV(`user_sdwt_prod,line_id,department`), 사용자 소속 CSV(`userid,user_sdwt_prod`) |
| 권한 구분 | 소속(사람당 SDWT 하나), 소속별 역할(SDWT별 등급), 앱 역할 세 가지. 별도 데이터 범위 역할(`data-all`)은 두지 않는다 |
| 소속 | 그룹 `/org/<팀>/<라인>/<SDWT>`(역할 하위 그룹 없음). 같은 라인 이름이 여러 팀에 있을 수 있고 SDWT는 전체 유일. 이름에 `/`·`:` 금지. 팀 = 사내 부서 `deptname`(IdP가 채우므로 권한관리 웹은 쓰지 않음). 목록 CSV의 `department` 열 = 부서명 |
| 소속별 역할 | client `org` 역할 `sdwt:<SDWT>:<등급>`, `team:<팀>:line:<라인>:<등급>`, `team:<팀>:<등급>`(라인·팀은 SDWT 역할을 포함하는 복합 역할). SDWT 역할은 위치를 넣지 않아 이동에도 이름이 같음. SDWT 그룹에 `sdwt:<SDWT>:user`를 연결해 소속하면 자동으로 일반. `make keycloak-org-sync`가 트리에 맞춤 |
| 소속 변경 규칙 | 이전 `/org` SDWT 그룹 탈퇴, 새 SDWT 그룹 가입, `user_sdwt_prod`·`line_id` 갱신. 소속별 역할은 유지 |
| 토큰 | `affiliation: {team, line, sdwt}`, `org_roles`(`sdwt:<SDWT>:<등급>` 목록. 라인·팀 역할은 SDWT 역할로 펼쳐져 나가고 이름은 빠짐), `resource_access.<clientId>.roles`. client scope `org-claims`가 발급하며 앱 client에 연결 |
| 앱 권한 | 앱 client 역할 `viewer` ⊂ `user` ⊂ `admin`. Portal은 `<기능>:<단계>`와 묶음 `all:<단계>`. 토큰 `resource_access.<clientId>.roles` |
| 역할 정의 | `deploy/keycloak/access/catalog.json`(서버 도구가 표준 라이브러리만 쓰므로 JSON) → `make keycloak-access-apply`. 없는 역할·포함 관계만 추가, 이전 역할은 경고 |
| 기본 권한 | `open` 앱·기능의 `viewer`를 realm 기본 역할에 넣음. `closed`는 부여받은 사람만 |
| SDWT 앱 역할 | `/org` SDWT 그룹에 앱 역할 연결(소속 구성원이 상속, 지원 인원은 제외) |
| 앱 판단 규칙 | SDWT S 데이터 = min(앱 역할, `org_roles` 중 `sdwt:S:<등급>`의 최댓값). S 역할이 없으면 볼 수 없음 |
| 권한관리 웹 앱 목록 | 적용 도구가 `/iam` 그룹 속성 `iam.catalog`에 255자 이하 조각으로 저장(앱·`org` client 내부 id 포함). 웹 재배포 없이 열 추가 |
| 웹의 org 역할 권한 | fine-grained admin permissions v2로 `/iam/platform-admins`에 `org` client의 view·manage·map-roles·map-roles-composite만 허용(`view-clients` 미부여) |
| 구현 원칙 | 방어용 부가 기능(대량 변경 차단 등)은 만들지 않는다 |
| 앱 판단 구현 | 공통 판단 함수·패키지를 두지 않는다. 각 앱이 [권한 모델](../../../apps/iam/README.md#권한-모델)의 규칙대로 토큰을 직접 해석한다 |

## 현재 상태

- 소속 트리 `/org/<팀>/<라인>/<SDWT>`와 CSV 도구 `deploy/keycloak/scripts/init_sdwt.py`, 소속별 역할 도구 `deploy/keycloak/scripts/org_sync.py`가 있다.
- 개발 Keycloak은 `/org` 트리·`org` client·FGAP·카탈로그가 적용돼 있다. realm JSON에는 Portal 개발용 이전 그룹(`/SDWT-A/…`)만 있고 `/org` 트리는 도구로 만든다.
- Portal은 아직 이전 경로 `/<SDWT>/<role>`만 해석한다. `affiliation`·`org_roles` 해석은 Portal 작업(Plane ESOP 계획 2단계)에서 한다. 이 계획은 Portal을 수정하지 않는다.
- 개발 Keycloak: `local/keycloak`(realm `portal`, `http://localhost:8180`). 운영 realm은 `etch`.

## 범위

수정 영역

- `deploy/iam/scripts/setup_keycloak.py`: `iam` public client(PKCE, 관리 API용 realm-management role scope), `/iam/platform-admins` 그룹과 관리 role, `org` client FGAP, realm 관리 이벤트
- `deploy/keycloak/scripts/org_sync.py`, `make keycloak-org-sync`·`keycloak-org-test`, `local/keycloak/scripts/seed_org_dummy.py`(`make local-keycloak-dummy`)
- `deploy/keycloak/access/catalog.json`, `deploy/keycloak/scripts/access_apply.py`, `make keycloak-access-apply`·`keycloak-access-test`
- `apps/iam/web`(신규): Vite + React + Tailwind, 런타임 설정 `config.js`
- `local/keycloak/k8s/realm-portal.json`: 개발용 `iam` client·관리자 그룹, 사용자 기본 역할
- 문서: `apps/iam/README.md`, `deploy/keycloak/docs/03-configure.md` 링크, `docs/agent/02-git-scopes.md`(`[iam]`)

수정하지 않을 영역(다음 단계)

- 컨테이너 이미지·`deploy/iam` Kubernetes 정의·`apps.json`·서버 검사·`local/iam` kind 배포
- 인사 동기화, 위임 관리, Airflow·Portal 코드 전환과 이전 역할 삭제

## 설계

- 로그인: `keycloak-js` 표준 흐름 + PKCE. 토큰의 `resource_access.realm-management.roles`에 `manage-users`가 없으면 "권한 없음"을 표시한다.
- `iam` client는 `fullScopeAllowed=false`이고 realm-management `view-users`·`query-users`·`query-groups`·`manage-users`만 scope로 허용한다. `webOrigins`는 IAM 주소로 제한한다.
- 화면
  - 권한: Portal 권한 매트릭스(`ScopePermissionMatrix`)와 같은 형식. 행은 사용자, 열은 카탈로그. 셀은 직접 역할, 유효 역할은 `/users/{id}/role-mappings/clients/{uuid}/composite`
  - 조직: 팀 필터 → 팀·라인·SDWT 트리(라인 버튼으로 범위 축소) → SDWT 상세(소속 구성원, 지원 인원, SDWT 앱 역할). 상세의 수정 버튼으로 등급 변경, 지원 역할 부여·회수, 소속 변경·해제, 앱 역할 연결, 같은 팀 안 라인 이동. SDWT 추가(그룹+org 역할)·목록 CSV 업로드는 모달
  - 사용자 패널: 매트릭스에서 이름을 누르면 소속 변경, 소속별 역할(SDWT·라인 전체·팀 전체) 부여·회수와 SDWT별 적용 결과, 세션 종료
  - 소속 업로드: 사용자 소속 CSV → 미리보기(현재→변경, 없는 사용자·SDWT) → 적용과 행별 결과
- 그룹 생성·소속 변경 계산은 순수 함수(`src/lib/plan.js`)로 두고 vitest로 검사한다.
- 사용자 수정은 전체 사용자 표현을 읽어 속성만 바꿔 저장한다(User Profile에서 다른 속성 유실 방지).

## 실행 단계

- [x] 1. Keycloak 준비 도구와 개발 realm
- [x] 2. 웹 골격·로그인·Admin API 클라이언트
- [x] 3. 조직 화면과 목록 업로드
- [x] 4. 사용자 화면과 소속 업로드
- [x] 5. 개발 Keycloak으로 브라우저 확인, 문서
- [x] 5-1. 앱 권한을 표준 RBAC로 확정: 카탈로그·적용 도구·기본 역할, 매트릭스 역할 처리, SDWT 앱 역할, 세션 종료, 인프라 확인 창
- [x] 5-2. 소속을 팀 → 라인 → SDWT 계층으로 변경(준비 도구·개발 realm·권한관리 웹), 드롭다운은 팀 → 라인 → SDWT 연결 선택
- [x] 5-3. 소속·소속별 역할·앱 역할 세 구분으로 확정: `/org` 소속 그룹, client `org` 역할과 `org-claims` scope, FGAP, 웹 전환, `data-all` 제거

- [ ] 6. 배포: 이미지(정적 파일 + env로 만드는 `config.js`), `deploy/iam/k8s`, `apps.json`·`all` 그룹 등록, `check-server.sh` 지원
  - 등록 전까지 `make audit-layout`이 `apps/iam`·`deploy/iam`을 앱 목록 밖 디렉터리로 보고한다.

후속: Airflow 전환(`oidc_claims.py` 역할 이름)과 이전 역할 삭제, Portal 전환(새 역할·`affiliation`·`org_roles` 해석, 로그인 시점 고정 제거, client `fullScopeAllowed=false`), 인사 동기화, 위임

## 검증

- `npm run test:run`, `npm run lint`, `npm run build` (`apps/iam/web`)
- 준비 도구: 임시 Keycloak 컨테이너에 적용·재실행, `make keycloak-access-test`
- 개발 Keycloak에서 로그인 → SDWT 추가·라인 이동 후 `make keycloak-org-sync` dry-run이 `변경 없음` → 등급·소속별 역할 변경 → 관리 이벤트 확인
- `make audit-docs`, `git diff --check`

## 위험과 대응

- 위험: 관리자 토큰이 브라우저에 있다. 대응: Keycloak 관리 화면과 같은 수준이며 client scope를 4개 role로 제한한다.
