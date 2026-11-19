# ExecPlan: Keycloak 기준 소속·권한과 Plane 기반 ESOP 재구성

## 목표

- Keycloak이 라인·SDWT 소속과 권한의 유일한 원본이다. Portal·Plane·Airflow는 Keycloak 값을 읽기만 한다.
- ESOP 목록과 발송 흐름은 유지하고, 발송 시 Jira 대신 Plane 작업 항목을 만든다.
- Plane 작업 항목의 상태를 ESOP 목록에 표시한다.
- 알림 대상은 하나 이상의 SDWT를 묶을 수 있고, 채널별 수신자를 선택할 수 있다.
- Plane은 Keycloak SSO로 로그인하며 프로젝트 멤버·역할은 Keycloak 그룹에서 자동으로 맞춘다.

## 확정 조건

| 항목 | 결정 |
| --- | --- |
| 범위 | Plane·ESOP와 Portal 계정 앱의 소속·권한 처리를 모두 Keycloak 기준으로 재구성 |
| Jira | 완전 제거 |
| Plane 발행 | 실제 발송 대상(dispatch)만 작업 항목으로 생성 |
| Plane 상태 | ESOP 목록에 표시. 닫힘에 따른 별도 업무 규칙은 두지 않음 |
| Keycloak 소속·권한 | 소속 그룹 `/org/<팀>/<라인>/<SDWT>`, 소속별 역할 client `org`(`sdwt:<SDWT>:<등급>`, 라인·팀 전체 역할) |
| 알림 대상 | 여러 SDWT를 묶은 대상 지원 |
| 수신자 | 채널별로 선택 가능 |
| Plane 로그인 | Keycloak OIDC. Plane CE에 패치로 추가 |
| Plane 의존 서비스 | PostgreSQL·Redis(Valkey)·RabbitMQ는 Plane 전용 |
| 파일 저장소 | 기존 `deploy/minio` 하나를 버킷·계정 분리로 공유(`plane`, `emails`, `profile`) |
| Plane 주소 | `plane.etch.samsungds.net`. 인증서 보유는 사용자 확인 |

## 현재 상태

- 선행 계획: [IAM 통합 권한 관리](iam-central-access.md). Keycloak 그룹 트리·앱 카탈로그·인사 소속 동기화·Portal 그룹 해석은 그 계획이 맡는다.
  이 계획의 1단계와 2단계의 그룹 해석 부분은 그 결과를 사용하고, Plane client는 카탈로그 규칙(`iam.managed`)을 따른다.
- Portal 화면 권한은 이미 로그인 토큰의 `groups`와 앱 역할로 판단한다: `apps/portal/api/api/account/services/keycloak_access.py`.
  현재 그룹 형식은 `/<SDWT>/<role>`이고 라인은 사용자 속성 `line_id`다.
- Keycloak 그룹 발급 scope는 `deploy/keycloak/k8s/claims/sdwt-access-scope.json`(`sdwt-access-v1`, claim `groups`, 전체 경로)이다.
  소속 속성 `user_sdwt_prod`·`line_id`는 관리자·최초 CSV로 채우며 소속 변경 시 그룹을 자동 부여하지 않는다: `deploy/keycloak/docs/03-configure.md`.
- 계정 앱 DB에는 소속·권한 모델이 남아 있다: `Affiliation`, `UserCurrentAffiliation`, `UserSdwtProdAccess`, `AccessScope`, `AccessPolicyRule`, `UserAccess`, `UserScopeAffiliationGrant`, `AccessAuditLog`, `UserSdwtProdChange`, `ExternalAffiliationSnapshot`.
  사용처는 대부분 `api/account` 내부이며 외부 사용은 `emails/services/mutations.py`(`UserSdwtProdChange`)와 Drone target source 값이다.
  `AccessScope`는 앱 카탈로그로 Keycloak 판정에서도 사용한다.
- SDWT 이름은 전체에서 유일하다(`account_affiliation`의 `uniq_acc_aff_usr_sdw_ci`).
- 사내 인사 소속은 Airflow `account_external_affiliations_sync` DAG가 Portal `/api/v1/account/external-affiliations/sync`로 보낸다.
- ESOP(web `line-dashboard`, api `drone`)
  - target 단위 채널 설정에 `jira_project_key`가 있다.
  - Jira 연동 코드는 `services/jira/*`(약 2,000줄)와 `views/jira.py`다.
  - 채널 값은 `jira`·`mail`·`messenger`다.
  - 수신자는 mail·messenger만 있고 account 사용자 pool에서 생성한다.
  - SOP의 `sdwt_prod`·`user_sdwt_prod`는 `DroneSopTargetMapping`으로 target에 연결된다.
- Portal은 운영 DB·서버에 적용된 적이 없어 데이터 이전·호환 migration이 필요 없다.
- Portal은 MinIO를 메일 자산(`emails` 버킷, `api/common/services/storage.py`)과 프로필 이미지(`<MINIO>/profile/<id>.png`, `web/src/lib/profileImage.js`)에 사용한다.

## 범위

수정 영역

- `deploy/keycloak`: 그룹 계층, 디렉터리 읽기용 service account client, Plane client, 그룹 트리 준비 도구
- `apps/plane`(신규): 고정 upstream 태그와 패치(OIDC 로그인, 로그인 시 그룹→프로젝트 멤버 반영, 필요 시 사용자·멤버 준비 API), 이미지 빌드 입력
- `deploy/plane`·`local/plane`(신규), `deploy/shared/apps.json`, `deploy/minio`(버킷·계정 추가)
- `apps/portal/api`: `account`(Keycloak 디렉터리 사본으로 축소), `drone`(대상·수신자 재설계, Jira→Plane), 연관 `emails`
- `apps/portal/web`: `line-dashboard`, 계정·권한 관련 화면
- `apps/airflow`: Keycloak 디렉터리·Plane 동기화 DAG
- `local/adfs_dummy`: Jira mock을 Plane mock으로 교체. `local/keycloak`: 개발용 그룹 트리
- 문서: `docs/features/{02-account,05-line-dashboard}.md`, `docs/concepts/03-integrations.md`, `docs/reference/01-configuration.md`, 인프라 문서, `docs/agent/02-git-scopes.md`(`[plane]`)

수정하지 않을 영역

- 사내 인사 소속을 Keycloak에 넣는 경로와 소속 변경 시 그룹 자동 변경 정책(사용자 결정 전). 그 전까지 그룹·속성은 Keycloak 관리 화면이나 준비 도구로 입력한다.
- ESOP 이외 Portal 기능의 업무 로직. 소속·권한 조회 방식만 바꾼다.
- Headlamp 그룹·Kubernetes 권한 계약

## 설계

### Keycloak 조직·권한 모델

[IAM 계획](iam-central-access.md)의 세 구분을 따른다. 원본 설명은 [권한관리 웹 문서](../../../apps/iam/README.md#권한-모델)다.

- 소속: 그룹 `/org/<팀>/<라인>/<SDWT>` 하나. 토큰 `affiliation: {team, line, sdwt}`
- 소속별 역할: client `org` 역할 `sdwt:<SDWT>:<등급>`, 라인·팀 전체 역할(`team:<팀>:line:<라인>:<등급>`, `team:<팀>:<등급>`)은 그 아래 SDWT 역할을 포함한다. 토큰 `org_roles`(펼쳐진 목록)
- 앱 역할: 앱 client 역할. 토큰 `resource_access.<clientId>.roles`
- 디렉터리 읽기 client: 동기화 작업이 사용자·그룹·멤버를 읽는 service account다. `view-users`·`query-groups` 수준이며 쓰기 권한은 없다.
- 그룹 트리(라인·SDWT 목록)는 Keycloak 관리 화면이나 준비 도구로 만든다. 입력 파일 형식은 실행 단계에서 정한다.

### Portal

- 권한: `keycloak_access`가 `affiliation`·`org_roles`를 해석해 `(line, sdwt) → role`을 만든다. 세션 snapshot 형식을 갱신한다.
- 디렉터리 사본: 다음 경우에 필요하다.
  - 로그인하지 않은 사용자가 관련된 작업. 예: 발송 수신자 계산, 수신자 선택 화면
  - 동기화 작업이 Keycloak에서 읽은 사용자·그룹·멤버 정보

  이를 위해 읽기 전용 테이블을 둔다. Portal 화면·API는 이 사본을 수정하지 않는다.
- 계정 앱 정리: 소속·권한을 DB에 저장하던 기존 모델은 사본과 앱 카탈로그만 남기고 제거한다. 대상은 다음과 같다.
  - 소속 목록·현재 소속
  - SDWT 권한, 정책·grant
  - 소속 변경 요청, 외부 스냅샷
  - 감사 로그(Keycloak 이벤트로 대체 여부는 실행 단계에서 확인)

  관련 API·화면·`emails` 의존도 함께 바꾼다.
- 외부 소속 동기화 API는 3번 결정 전까지 유지 여부를 보류한다. 원본이 Keycloak이므로 Portal DB에 소속을 쓰는 동작은 남기지 않는다.

### ESOP 대상·수신자

- 알림 대상(target)은 이름과 하나 이상의 SDWT 그룹으로 구성한다. 라인은 SDWT 그룹 경로에서 얻는다.
- SOP→대상 연결(`DroneSopTargetMapping`)은 유지한다.
- 채널별 수신자 선택
  - `role`: 대상 SDWT 그룹 멤버 중 지정 역할 이상
  - `selected`: 대상 그룹 멤버 중 개별 선택

  그룹에서 빠진 사용자는 발송 시 자동 제외한다. 그룹 밖 사용자는 선택할 수 없다.
- 채널: `plane`·`mail`·`messenger`. `jira` 값과 Jira 설정·코드·env(`DRONE_JIRA_*`)를 제거한다.

### Plane

- 유료판은 사용하지 않는다. workspace는 하나이며 이메일·magic link 가입과 사용자 workspace 생성을 끄고 OIDC 로그인만 허용한다.
- 프로젝트: Keycloak SDWT 그룹(`/<팀>/<라인>/<SDWT>`)마다 비공개 프로젝트 하나를 미리 만든다. 이름은 `L1 · SDWT_A`다.
  - Portal 디렉터리 동기화가 Keycloak 그룹 트리를 읽어 공개 API로 없는 프로젝트를 만든다.
  - `SDWT → project_id` 연결은 Portal 사본에 저장한다. 그룹이 사라진 프로젝트는 삭제하지 않고 보관 상태로 둔다.
- 멤버: `org_roles`의 SDWT별 최고 등급으로 admin→Admin, user→Member, viewer→Guest다. 라인·팀 전체 역할은 토큰에서 SDWT 역할로 펼쳐져 같은 규칙을 따른다.
  - 첫 로그인·매 로그인: Plane OIDC 패치가 토큰 `org_roles`로 workspace 가입과 소속 프로젝트 멤버·역할을 즉시 맞춘다.
    Plane 사용자는 첫 로그인 때 생기므로, 로그인 전 사용자를 미리 배치할 필요가 없다.
  - 주기 보정: Portal 디렉터리 동기화(Airflow trigger)가 이미 있는 Plane 사용자의 멤버 추가·역할 변경·제거를 공개 API로 맞춘다.
    공개 API에 필요한 멤버 기능이 없으면 그 기능만 패치에 추가한다.
- 여러 SDWT 대상의 작업 항목 위치는 결정 대기다. 후보는 SDWT 프로젝트마다 하나씩 생성하는 것과 대표 SDWT 프로젝트 하나에 생성하는 것이다.
- 작업 항목 생성
  - 발송 dispatch 단위로 만든다. `external_id`로 같은 항목을 두 번 만들지 않는다.
  - 본문은 기존 HTML 템플릿과 CTTTM URL 보강을 재사용한다.
  - 호출 제한(429) 응답의 reset 시각을 기준으로 재시도한다.
- 상태 반영
  - Plane webhook을 서명 검증으로 받는다. 세션 인증을 쓰지 않는다.
  - 상태 그룹(backlog/unstarted/started/completed/cancelled)·이름·변경 시각을 저장한다.
  - 놓친 변경은 주기 대조로 보정한다. ESOP 목록에는 dispatch별 상태와 링크를 표시한다.
- 알림: Plane 자체 메일은 사용하지 않는다(SMTP 없음). Portal mail·messenger가 Plane 링크를 포함해 보낸다.
  Plane 생성이 실패해도 mail·messenger는 링크 없이 발송한다.
- 소스: upstream 고정 태그와 패치 파일을 `apps/plane`에서 관리한다. 수정판 사용자에게 소스 위치를 안내한다(AGPL).

### 배포·env·auth 영향

- 새 Keycloak client: `plane`(OIDC, `sdwt-access-v1` scope 포함), 디렉터리 읽기 service account
- 새 env 그룹: Plane API·공개 URL·workspace·webhook secret·호출 제한, Keycloak 디렉터리 client, MinIO Plane 계정
- 새 Portal API
  - Plane webhook 수신
  - 디렉터리 사본 갱신 trigger와 Plane 대조 trigger(Airflow Bearer)
- 변경되는 공개 API
  - Jira 관련 `line-dashboard` API 제거
  - 수신자·대상 API 재설계
  - 계정 소속·권한 API 축소

## 실행 단계

마일스톤마다 검증 후 커밋한다.

- [ ] 0. 사전 확인
  - Plane 버전 고정. 다음 항목을 확인한다.
    - 작업 항목 API와 `external_id`
    - 프로젝트 멤버 API 존재 여부
    - webhook 서명과 내부 주소 허용 여부
    - 호출 제한 env
    - MinIO 외부 엔드포인트와 presigned URL 동작
    - OIDC 패치 지점
  - 이미지 빌드 경로(CP1 BuildKit, 사내 npm·PyPI 미러)와 주소 인증서·DNS 상태를 확인한다.
- [ ] 1. Keycloak 조직 모델
  - 그룹 계층과 라인 관리자 그룹을 만든다.
  - 그룹 트리 준비 도구, 디렉터리 읽기 client를 만든다.
  - `local/keycloak` 개발 그룹 트리를 만든다.
- [ ] 2. Portal 권한·디렉터리 사본
  - 새 그룹 해석과 세션 snapshot을 반영한다.
  - 디렉터리 사본 모델·갱신 API·Airflow DAG를 만든다.
- [ ] 3. ESOP 대상·수신자 재설계
  - 다중 SDWT 대상, 채널별 수신자 선택(`role`/`selected`)을 만든다.
  - 사본 기준 수신자 계산, 화면을 바꾼다.
- [ ] 4. Jira 제거와 Plane 채널(mock 기준)
  - Plane client·프로젝트·작업 항목 생성을 만들고 `adfs_dummy` Plane mock을 둔다.
  - 목록 Plane 칸·설정 화면을 바꾼다.
- [ ] 5. 상태 반영: webhook 수신, 주기 대조 DAG, 목록 상태 표시
- [ ] 6. Plane 패치·이미지: OIDC 로그인과 로그인 시 그룹→workspace·프로젝트 멤버 반영을 만든다. 공개 API에 멤버 제거·역할 변경이 없을 때만 해당 API를 추가한다.
- [ ] 7. Plane 배포
  - `deploy/plane`(전용 PostgreSQL·Redis·RabbitMQ, 공용 MinIO `plane` 버킷)을 만든다.
  - ingress, Keycloak client Job, `apps.json`을 맞추고 인프라 문서·`pending.md`를 갱신한다.
- [ ] 8. Plane 프로젝트·멤버 동기화: Keycloak SDWT 그룹 → 프로젝트 사전 생성, 기존 사용자 멤버·역할 보정
- [ ] 9. 계정 앱 정리
  - DB 소속·권한 모델과 관련 API·화면·`emails` 의존을 제거한다.
  - 사본·앱 카탈로그만 남긴다.
- [ ] 10. 문서·scope·평가 시나리오 갱신과 전체 검증

## 검증

- API: `make test-api check-api makemigrations-check`. 다음 항목을 테스트한다.
  - 새 그룹 해석(라인 관리자 포함)
  - 디렉터리 사본 갱신
  - 다중 SDWT 수신자 계산
  - Plane 생성 중복 방지·429 재시도
  - webhook 서명 실패·성공, 상태 대조
- 경계: `make audit-api-boundary audit-web-boundary audit-ui`
- 로컬 흐름: mock으로 다음을 확인한다. `make k8s-render-local`, `make env-profile-key-check ENV_APP=portal ENV_PROFILE=local`
  - SOP 수집 → 발송 → Plane 항목 생성 → 상태 변경 → ESOP 표시
- 서버 정의: `make server-check APP=plane PROFILE=prod`, `make server-check APP=portal PROFILE=prod`, `make server-check APP=keycloak PROFILE=prod`
- 문서: `make audit-docs`, `node --test apps/tooling/tests/server-checkout.test.cjs`
- 실제 서버 적용·로그인·webhook 수신은 정적 검사와 별도로 확인하고 보고한다.

## 위험과 대응

- 위험: 그룹 변경이 Plane에 늦게 반영된다(로그인 시점에만 반영).
  대응: 주기 멤버 동기화와 짧은 Plane 세션 유지 시간을 함께 쓴다.
- 위험: Plane upgrade 시 패치 충돌.
  대응: 패치를 OIDC provider·멤버 반영으로 최소화하고 upstream 태그를 고정한다.
- 위험: Plane이 내부 주소 webhook을 거부한다.
  대응: 패치로 허용하거나 주기 대조만으로 상태를 반영한다.
- 위험: 발송 집중 시 Plane 호출 제한.
  대응: 서비스 토큰·제한 env를 조정하고 429 reset 기준으로 재시도한다. 대기 중에도 mail·messenger는 진행한다.
- 위험: 계정 앱 정리 범위가 커서 다른 기능이 깨진다.
  대응: 9단계를 마지막에 두고 사용처를 `rg`와 boundary audit으로 확인한다. 기능별 테스트를 통과시킨 뒤 제거한다.
- 위험: 소속 입력 경로(3번)가 미정이라 초기 그룹 데이터가 비어 있다.
  대응: 준비 도구로 수동 입력한다. 결정 후 외부 소속 DAG의 대상을 Keycloak으로 바꾸는 안을 검토한다.
