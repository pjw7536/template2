# ExecPlan: Airflow–Keycloak 로그인 연동

## 목표
- Airflow 2.11.0 웹 로그인을 기존 Keycloak realm의 전용 `airflow` client로 통합한다.
- Keycloak의 Airflow client 역할로 접근을 결정하고, 로컬에서 검증한 동일 코드를 서버에 배포한다.
- 현재 요청은 확정한 설계의 구현과 로컬 적용이다. 사내 서버는 접근 가능한 context와 실제 운영 입력이 없으므로 배포 준비 코드·절차를 제공하고 로컬 실행과 구분한다.
- 사용자 지시에 따라 기존 브라우저 세션 이관·즉시 폐기·통합 로그아웃은 고려하지 않는다.

## 현재 상태
- `deploy/airflow/helm/values.yaml`: Airflow 2.11.0, LocalExecutor, Basic API 인증 및 Secret 기반 관리자 초기화.
- `apps/airflow/image/Dockerfile`: DAG·플러그인·`bootstrap-user.py`를 이미지에 포함하며 별도 SSO 설정은 없다.
- `apps/airflow/image/bootstrap-user.py`: default_pool 설정과 DB 관리자 생성. 기존 관리자는 보존한다.
- 로컬 `kind-tailwind-local`의 Airflow webserver에서 FAB provider 1.5.3을 확인했다. 해당 Basic 인증 구현은 OAuth 모드에서도 `auth_user_db`를 호출할 수 있다.
- `local/shared/scripts/k8s_config.py`: Portal의 `AIRFLOW_USERNAME/PASSWORD`에 로컬 Airflow 관리자 계정을 전달한다. credentials 파일은 현재 정확한 키 집합을 요구한다.
- `apps/portal/api/api/drone/services/airflow.py`: Portal → Airflow 호출에 사용자명·비밀번호를 사용한다.
- Airflow → Portal의 `AIRFLOW_TRIGGER_TOKEN`은 별도의 기존 계약이다.
- 로컬 Keycloak realm은 `portal`, 브라우저 issuer는 `http://localhost:8180/realms/portal`이다. 기존 Portal도 브라우저 주소와 Pod 내부 token/JWKS 주소를 분리한다.
- 서버 topology 원본은 `deploy/shared/docs/infrastructure/cluster.md`. 목표 URL은 `https://etch.samsungds.net/airflow`이며 운영 realm 이름은 서버 Keycloak 설정에서 읽는다.
- 2026-09-26 로컬 Airflow Pod와 health는 정상으로 확인했다. 서버 배포·로그인 상태를 조회한 결과는 아니다.

## 범위
- Airflow 이미지의 FAB 보안 설정, Keycloak client 등록, 서버 env·Secret·Helm 연결, 로컬 realm·실행 연결, 관련 테스트·운영 문서.
- 기존 DB·DAG·Connection·Variable·Fernet 키·pool 설정을 유지한다. Airflow DB 스키마를 추가하지 않는다.
- Portal 업무 권한·SDWT·기존 realm·사내 IdP 설정을 변경하지 않는다. Airflow 3 업그레이드, Keycloak 네이티브 auth manager 교체, DAG별 조직 격리는 포함하지 않는다.
- 이번 단계에서 Portal API 인증을 OAuth client credentials로 바꾸지 않는다. 새 service account나 비밀번호 회전은 후속 개선으로 구분한다.

## 설계

### 1. 로그인 흐름과 사용자 식별
1. `/airflow`의 미인증 사용자는 Airflow 로그인 화면의 Keycloak 로그인으로 이동한다.
2. 기존 realm에 Authorization Code 방식으로 로그인한다. 이미 Keycloak에 로그인했다면 그 SSO 상태를 활용한다.
3. callback에서 code를 교환하고 OIDC ID Token의 서명·issuer·audience·유효기간·nonce 및 OAuth state를 검증한다. Authlib의 검증 흐름을 사용하고 검증 없는 JWT decode는 금지한다.
4. 검증된 ID Token의 `resource_access.airflow.roles`를 읽어 접근을 판정한다. client ID를 바꾸면 그 키도 설정값을 사용한다.
5. 정상적인 OIDC 인증을 완료한 모든 사용자의 FAB 계정을 생성·갱신하고 기본 Viewer 권한으로 세션을 만든다. 명시적인 User·Admin 역할이 있으면 해당 권한도 적용한다. 이메일·표시 이름으로 기존 DB 계정과 자동 병합하지 않는다.
6. FAB username은 검증된 `iss`와 `sub`의 조합에서 만든 고정 길이 식별자(`kc_` + SHA-256 hex)로 저장한다. client에 공급한 이름·이메일은 표시 속성이다. 필수 신원 값이 없으면 로그인 오류로 처리한다.

`AUTH_TYPE=AUTH_OAUTH`, `AUTH_USER_REGISTRATION=True`, `AUTH_ROLES_SYNC_AT_LOGIN=True`를 사용한다. 등록 기본 역할은 `Viewer`로 둔다. 이 기본 권한은 설정된 realm에서 OIDC 인증을 완료한 사용자에게만 적용한다. 익명 사용자의 `Public` 역할에는 권한을 부여하지 않는다.

### 2. 역할 계약

Airflow 내장 역할 이름을 Keycloak client role에도 그대로 사용한다. 별도의 `airflow-admin` 같은 역할 이름을 만들지 않는다. FAB 연결 설정에서 허용한 동일 이름의 역할만 적용하며, 토큰에 담긴 임의 역할을 생성하지 않는다. 기존 Portal 역할이나 realm 관리 역할은 Airflow 권한으로 해석하지 않는다.

| Keycloak client role | Airflow 역할 | 사용 목적 |
| --- | --- | --- |
| `Viewer` | `Viewer` | DAG·실행 결과 조회 |
| `User` | `User` | DAG 실행 등 일반 운영 |
| `Admin` | `Admin` | Airflow 전체 관리 |
| 없음·알 수 없는 역할만 존재 | `Viewer` | 인증된 모든 사용자에게 기본 조회 허용 |

- 기본 Viewer와 여러 허용 역할에 대응하는 FAB 역할의 합집합으로 동기화한다. 로그인 시 과거 FAB 역할을 남기지 않는다.
- `User`는 내장 역할이므로 개별 DAG에만 제한되는 권한이 아니다. 실제 설치 버전의 허용 작업을 테스트로 확인한다. SDWT 기반 데이터 격리를 제공한다고 간주하지 않는다.
- 기존 사용자의 User·Admin 역할을 제거하면 다음 로그인부터 Viewer로 내려간다. 기본 조회 권한은 개별 Airflow 역할 제거로 회수되지 않는다. 계정 비활성화는 Keycloak의 기존 정책을 따르며 다른 앱 로그인에도 영향을 준다. 기존 세션의 즉시 권한 회수는 범위 밖이다.
- 운영 사용자의 역할 부여는 명시적으로 수행한다. client 생성 시 전체 realm 사용자나 Portal 관리자에게 Airflow 역할을 자동 부여하지 않는다.
- 초기 운영은 필요한 관리자에게 `airflow` client의 `Admin` 역할을 직접 부여한다. 일반 운영자가 필요해지면 `User`를 직접 부여한다. 조회 사용자는 별도 역할 할당이 필요 없다. 사용자 관리 화면에서는 용도에 맞는 역할 하나를 부여하는 것을 기본으로 한다.
- 조직별 그룹과 `/airflow/admins` 같은 관리 그룹을 이번 구현에서 만들거나 요구하지 않는다. 추후 관리 인원이 늘면 Keycloak 그룹에 동일 client role을 연결하는 방식으로 운영만 확장할 수 있다. Airflow의 역할 판정 코드는 바뀌지 않는다.
- 사용자 역할 부여·회수는 Keycloak에서 관리하고 각 내장 역할의 기능 권한은 Airflow에서 유지한다. SSO 사용자의 역할을 Airflow에서 별도로 수동 부여하지 않는다.

### 3. Keycloak client와 claim
- 기존 realm에 confidential client `airflow`를 생성하고 Standard Flow를 켠다. Implicit Flow, Direct Access Grants, Service Accounts는 끈다.
- scope는 `openid profile email`. 전용 client-role mapper가 해당 client 역할만 `resource_access.${client_id}.roles` 문자열 배열로 ID Token에 포함하도록 한다. Access Token에도 같은 claim을 발급할 수 있으나 Airflow 웹 권한의 원본은 검증된 ID Token이다.
- Airflow client에는 Portal의 SDWT·조직·groups mapper를 추가하지 않는다. realm 공통 설정으로 해당 claim이 발급되더라도 Airflow는 이를 권한 판정에 사용하지 않는다. Airflow 역할 예시는 `{"resource_access":{"airflow":{"roles":["Admin"]}}}`이며 `portal.roles`에 Airflow 자체 권한을 넣지 않는다.
- 등록 도구는 Airflow 소유 client·role·mapper만 생성/갱신한다. 기존 client secret과 사용자 역할 할당은 보존한다. realm 전체 import로 운영 설정을 덮어쓰지 않는다.
- callback은 정확한 URL만 허용한다. 로컬: `http://localhost:8080/airflow/oauth-authorized/keycloak`, 서버: `${AIRFLOW_WEBSERVER_BASE_URL}/oauth-authorized/keycloak`.
- prefix·후행 slash 정규화 후 실제 callback과 일치하는지 검증한다. wildcard redirect와 wildcard Web Origins는 사용하지 않는다.
- client secret은 앱 전용이다. Portal·Headlamp·사내 IdP client secret을 재사용하지 않는다.

### 4. 설정·네트워크 계약

아래 항목은 추가 예정인 Airflow 소유 env 계약이다. URL·realm·credential은 Python에 하드코딩하지 않는다.

| 설정 | 의미 |
| --- | --- |
| `AIRFLOW_AUTH_MODE` | `db` 또는 `keycloak`. 이관 전 호환값은 db, 로컬 검증과 서버 전환 시 keycloak을 명시 |
| `AIRFLOW_OIDC_ISSUER` | 검증할 공개 realm issuer |
| `AIRFLOW_OIDC_CLIENT_ID` | 전용 client ID, 기본 airflow |
| `AIRFLOW_OIDC_CLIENT_SECRET` | client 인증 비밀값 |
| `AIRFLOW_OIDC_BACKCHANNEL_BASE_URL` | 선택적인 Pod 접근용 realm base URL. 비우면 issuer 사용 |
| `AIRFLOW_OIDC_CA_BUNDLE` | 선택적인 컨테이너 내 신뢰 CA bundle 경로 |

- 공개 issuer에서 authorization URL을 만들고, backchannel base에서 token·JWKS 주소를 구성한다. Keycloak 고정 endpoint와 공개 issuer·RS256 메타데이터를 명시하여 원격 discovery 요청 없이 Authlib를 설정한다. discovery에 포함된 공개 localhost 주소를 Pod에서 그대로 호출하지 않는다. issuer 검증값은 backchannel을 쓰더라도 바꾸지 않는다.
- 로컬 backchannel은 Keycloak Service의 실제 namespace를 포함한 내부 DNS를 사용한다. Airflow namespace에서 `keycloak` 단축 DNS가 해석된다고 가정하지 않는다.
- 서버는 HTTPS와 CA 검증이 필수다. 사내 CA는 신뢰 bundle로 마운트한다. TLS 검증 생략 옵션을 만들지 않는다. HTTP 예외는 명시적 로컬 설정에서만 허용한다.
- JWKS는 kid 기반으로 선택하고 갱신한다. 승인한 서명 알고리즘만 허용한다. 인증 서버 장애 시 로그인은 실패하며 DB 로그인으로 자동 우회하지 않는다.
- keycloak 모드는 필수 설정 누락 시 배포 검사에서 실패한다. 설정 import 시 네트워크 요청을 하지 않아 migration·scheduler 시작을 인증 서버 가용성에 결합하지 않는다.
- client secret은 Kubernetes Secret으로 전달한다. 렌더 결과·Helm values·로그·이미지에 기록하지 않는다. CA 설정은 파일 마운트와 env를 함께 검사한다.

### 5. API 인증과 초기화
- FAB의 Basic API 인증과 session API 인증을 명시적으로 설정한다. 웹 로그인 OAuth 설정과 API 인증 backend는 분리한다.
- 기존 Portal의 `AIRFLOW_BASE_URL`, `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` 계약을 유지한다. 현재 로컬 DB 관리자를 API에 사용하는 상태도 이번 단계에서는 유지하며, 최소 권한 전용 API 계정은 후속 과제로 남긴다.
- OAuth 생성 계정에는 DB 비밀번호를 설정하지 않는다. Basic 인증이 이 계정으로 성공하지 않는지 검사한다.
- `bootstrap-user.py`의 기존 DB 관리자 생성과 pool 초기화를 유지한다. OAuth 모드에서는 해당 관리자 비밀번호로 웹 로그인을 제공하지 않지만 API 인증에는 사용할 수 있다.
- Airflow → Portal token 계약을 유지한다. 양방향 호출 회귀를 검증한다.
- 인증 mode 롤백은 이전 이미지·env로 명시적으로 수행한다. DB·Fernet 키·기존 계정은 삭제하지 않는다.

### 6. 파일 소유권과 구현 위치

| 영역 | 변경 예정 |
| --- | --- |
| `apps/airflow/image/` | `webserver_config.py` 및 보안 매니저 모듈 추가, 이미지 COPY, 필요한 의존성 버전 확인 |
| `apps/airflow/tests/` | claim 검증·사용자 식별·역할 동기화·거부 동작 테스트 |
| `deploy/airflow/scripts/manage.py` | env 키 집합·검증·Secret·CA 마운트·빌드 입력 검사 확장 |
| `deploy/airflow/helm/values.yaml` | 웹 설정 로딩·API 인증 backend 명시, 기존 executor 유지 |
| `deploy/airflow/k8s/jobs/keycloak-client/` | Airflow client·mapper·role 등록 Job과 안내 추가, Portal 소유 Job을 의존하지 않음 |
| `deploy/airflow/env/`, `deploy/airflow/README.md`, `deploy/keycloak/09_APP_CONNECTIONS.md` | 설정과 연결·검사·롤백 절차 |
| `local/shared/scripts/k8s.py`의 client 초기화 | 새 환경·기존 realm 모두 동일 등록 도구 사용, 로컬 테스트 역할 할당 |
| `local/shared/scripts/k8s_config.py`, `k8s.py` | 로컬 OIDC 값·Secret 연결, 기존 realm에 대한 멱등 client 등록, 실행 순서 |
| `local/airflow/`, `local/README.md`, `Makefile` | 로컬 override·사용 안내·명시적 client 등록 진입점 |
| `apps/tooling/tests/`, `docs/configuration.md` | 서버 경계·env 동기화·회귀 검증 및 계약 문서 |

- 새 보안 모듈의 import 경로는 실제 이미지에서 검증한다. Airflow 2.11.0/FAB 1.5.3 조합을 기준으로 하며 의존성 설치가 Airflow를 자동 업그레이드하지 않게 제한한다.
- 이미 존재하는 로컬 realm은 `--import-realm`으로 갱신되지 않으므로 명시적인 멱등 등록을 사용한다. 로컬의 테스트 사용자 역할은 로컬 전용 단계에서만 부여한다.
- `credentials.env`에는 누락된 새 client secret만 추가하는 이관을 구현한다. 기존 DB 비밀번호·Fernet 키를 재생성하지 않고 0600을 유지한다.
- 서버 env 키 계약과 로컬 합성 입력을 함께 변경한다. 서버 검사·배포는 계속 `apps/airflow` 소스와 `local/` 없이 동작해야 한다.

## 실행 단계
- [x] 현재 Airflow 인증·Portal API·로컬 Keycloak 계약 조사 및 설계 작성.
- [x] 구현 시작 시 각 수정 영역의 지침과 `offsite-dev-contract-sync` 스킬 적용.
- [x] 실제 이미지의 Authlib·FAB 검증 API와 패키지 버전을 확인하고 보안 매니저·단위 테스트 구현.
- [x] env·Secret·CA·client 등록·Helm 연결 및 공통 검사 확장.
- [x] 로컬 기존 realm과 credentials를 보존하며 전용 client 추가, Airflow 이미지 재빌드.
- [x] 관리자·일반 사용자·명시적 역할 없는 사용자의 기본 조회 로그인과 API 회귀 검증.
- [ ] 사내 서버 후속: 실제 운영 env·이미지·TLS·context 준비 후 client 등록 → render → airflow-check → airflow-up 수행. 현재 환경에서 서버 접근·배포는 수행하지 않았다.
- [ ] 사내 서버 후속: 실제 로그인·권한 거부·DAG 조회·Portal API 호출을 확인하고 운영 문서에 결과 기록.

## 검증
- 구현 검증: 아래 진행 기록의 로컬 실행 결과를 기준으로 한다. 서버 배포 성공과 구분한다.
- 구현 단위 테스트: 올바른/잘못된 issuer·audience·서명·만료·nonce/state, 누락 sub, 잘못된 role 자료형, 타 client·realm 역할 거부, 역할 삭제·변경, 동일 이메일의 사용자 분리, DB 관리자와 충돌 방지.
- 실패 검증: Keycloak/JWKS 장애·인증서 오류 때 로그인 거부, 토큰·secret 로그 노출 없음, 인증 실패 사용자는 미등록. 정상 인증된 역할 없는 사용자는 Viewer로 등록한다.
- 로컬 통합: `/airflow` prefix callback, Keycloak 로그인 후 각 FAB 역할 확인, 역할 없는 사용자의 조회 허용·변경 작업 거부, 익명 접근 거부, 새 세션 로그인 시 역할 갱신, API Basic·웹 session 인증 및 Airflow → Portal token 회귀.
- 등록 도구: 최초 등록·재실행·secret 보존·타 client 미변경·기존 realm 보존·로컬 신규 secret만 추가.
- `python3 -m unittest discover -s apps/airflow/tests -v`
- `node --test apps/tooling/tests/airflow-deployment.test.cjs apps/tooling/tests/app-layout.test.cjs apps/tooling/tests/server-checkout.test.cjs`
- `make env-profile-key-check ENV_APP=airflow ENV_PROFILE=prod`, `make k8s-check`, `make server-check APP=airflow PROFILE=prod`
- 기존 Portal 호출 테스트와 필요한 로컬 Airflow 통합 시나리오만 실행한다. Pod Ready·health 성공과 OIDC 로그인 성공은 별도로 기록한다.

## 위험과 대응
- 로컬 공개 issuer의 localhost는 Pod의 localhost와 다르다. backchannel을 분리하고 issuer는 공개값으로 고정 검증한다.
- 기본 Viewer는 인증을 완료한 사용자에게만 부여한다. issuer·서명·claim 형식 오류를 역할 누락으로 취급해 조회를 허용하지 않는다. 역할 claim이 없거나 빈 배열이면 정상적인 기본 Viewer 대상이며, 타 client·realm 역할은 추가 권한으로 해석하지 않는다.
- 기존 DB 계정과 SSO 사용자의 이름·이메일 충돌을 자동 병합하지 않는다. 신원 키는 issuer/sub로 고정하고 충돌 시 오류를 명확히 기록한다.
- 관리자 역할은 모든 DAG와 Airflow 관리 기능을 허용한다. 그룹 단위 DAG 격리는 별도 설계가 필요하다.
- 현재 사용자 변경이 Portal·Keycloak·로컬 도구에 존재한다. 구현 시 해당 변경을 보존하고 이 설계의 변경만 반영한다.

## 진행 기록
- 2026-09-26: 사용자 요청에 따라 기존 세션 처리를 제외한 설계를 작성했다. 로컬 FAB 1.5.3 Basic 인증 코드를 읽어 OAuth와 DB API 인증의 병행 가능성을 확인했다. 구현·서버 배포는 미실행이다.
- 2026-09-26: 후속 논의에 따라 역할을 Airflow 내장 이름인 Admin·User·Viewer로 통일했다. 조직·관리 그룹을 요구하지 않고 Keycloak 사용자에게 전용 client role을 직접 부여하며, 초기 운영은 필요한 관리자에게 Admin을 부여하는 방식으로 단순화했다.

- 2026-09-26: 사용자 지시에 따라 설정된 Keycloak realm에서 정상 로그인한 모든 사용자에게 Viewer를 기본 부여하도록 변경했다. User·Admin만 별도 부여하며 역할 제거 시 Viewer로 복귀한다. 익명 조회는 허용하지 않는다.

- 2026-09-26 구현: FAB OAuth callback에서 Authlib 검증을 사용하고 토큰 로그·세션 저장을 생략했다. 전용 client 역할과 기본 Viewer를 적용하며 Basic·session API 인증을 명시했다.
- 로컬 새 환경과 기존 환경은 공통 Python client 등록 도구를 호출한다. 중복 realm JSON client 정의는 추가하지 않았다. 운영 도구는 master realm 관리자 API로 등록하며 자동 사용자 권한 부여는 로컬 두 계정에만 적용한다.
- `make k8s-rebuild APP=airflow` 완료. 기존 DB·Fernet 키를 유지하고 누락된 OIDC secret만 추가했다. 실제 로그인에서 90000001=Admin+Viewer, 90000003=User+Viewer, 90000005=Viewer를 확인했다. User 제거 후 새 로그인에서 Viewer로 복귀하고 원래 역할을 복원했다.
- 검증: Airflow 소스 단위 검사 9개, 이미지 안의 Authlib 프로토콜 검사 2개(오류 token 8개 하위 사례), 배포 단위·실제 Helm 검사 28개, 로컬 credential·Secret 검사 3개, Node 배포·서버 경계 검사 23개 통과. `make k8s-check`, 서버 정적 검사, env 키 검사 통과.
- 실제 연동: 익명 API 거부, Viewer의 관리 자원 접근 거부, 기존 Basic API 인증, Portal의 Airflow 조회 통과. 대표 email_outbox_process DAG를 실행해 Airflow → Portal → RAG Outbox 처리와 Portal DAG 조회까지 통과했고 DAG의 기존 일시정지 상태를 복원했다.
- 사내 서버는 실제 env·인증서·이미지·context를 이 작업에서 확인하지 않았으므로 미배포다. 서버 SSO 입력과 등록·검사·배포 안내를 제공했다. 자동 commit/push는 수행하지 않았다.

## 참고 자료
- [FAB 웹 인증 및 Keycloak 예제](https://airflow.apache.org/docs/apache-airflow-providers-fab/1.5.1/auth-manager/webserver-authentication.html): OAuth 설정·보안 매니저 확장·로그인 역할 동기화의 근거. 예제의 claim·기본 권한 정책은 본 설계로 대체한다.
- [Airflow 2.11 API 인증](https://airflow.apache.org/docs/apache-airflow/2.11.0/security/api.html): API 인증의 auth manager 책임.
- 저장소 기준: `deploy/airflow/README.md`, `deploy/keycloak/09_APP_CONNECTIONS.md`, `local/README.md`, `deploy/shared/docs/infrastructure/cluster.md`.
