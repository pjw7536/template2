# ExecPlan: SDWT 하위 그룹 기반 공통 권한

## 목표

- 실제 소속은 사용자 속성으로, 접근 권한은 Keycloak의 `/{SDWT이름}/{등급}` 그룹으로 관리한다.
- 한 SDWT의 등급을 이 계약에 연결된 모든 업무 앱에 동일하게 적용한다. 앱이 늘어도 권한 그룹은 추가하지 않는다.
- 운영자는 Keycloak 기본 UI에서 그룹 가입·탈퇴로 권한을 관리한다. 별도 관리 UI, Client Role, Composite Role, SPI를 추가하지 않는다.
- 상태: **Keycloak 초기 설정 스크립트 구현·로컬 실제 Keycloak 검증 진행. Portal 판정 전환·운영 적용은 미완료**.
- 이 문서는 2026-09-25 최종 합의를 기록한다. 기존 `keycloak-organization-authorization.md`의 고정 SDWT ID, 조직 속성 상속, 앱별 역할·예외 그룹 설계를 대체한다. 과거 문서의 업무별 조사 결과를 새 정책의 확정 사항으로 간주하지 않는다.

## 현재 상태

- `deploy/keycloak/k8s/claims/account-user-profile.json`에 선택적 `user_sdwt_prod`, `line_id`가 있으며 관리자만 편집한다.
- `deploy/keycloak/k8s/claims/sync-oidc-claim-mappers.sh`가 소속을 Portal 토큰에 발급한다. `scripts/init_sdwt.py`가 SDWT 그룹과 공통 scope·선택 client·신규 사용자를 초기 등록한다.
- 현재 Keycloak username은 EPID이며 기존 출력 claim은 `userid`다. 설명 예시의 `epid`를 새 claim 이름으로 도입하지 않는다.
- `apps/portal/api/api/auth/services/oidc_claims.py`는 사내 신원 claim을 변환하지만 그룹 권한을 수신하지 않는다. 현재 Portal 사용자 연결은 sabun 기준이고 EPID는 avatarid에 저장된다.
- `apps/portal/api/api/auth/services/oidc.py`는 검증한 로그인 정보로 Django 세션을 생성한다. Keycloak 토큰 수명만 줄여서는 기존 Django 세션 권한이 5분 안에 회수되지 않는다.
- `apps/portal/api/api/account/services/access_runtime.py`, `access.py`, `data_scope.py`가 Portal의 앱 접근·SDWT 역할·데이터 범위를 각각 판정한다.
- 작업 트리의 `register_reference_users`는 Portal DB 등록 명령이다. 이를 실행해도 Keycloak 계정이나 그룹은 생성되지 않는다.
- 작업 트리의 migration 0007은 기존 Portal 권한 보존용이며 새 그룹 정책으로 전환하는 migration이 아니다.
- 기존 Headlamp 그룹은 클러스터 권한이다. SDWT 업무 권한과 합치지 않는다.

## 범위

- 이번 구현: Keycloak 그룹·mapper·등록 도구, Make 진입점, CSV 예시, 로컬 scope, 테스트·운영 안내.
- 후속 구현: Portal 권한 수신·갱신·판정, 관련 UI, 기존 권한 이관과 실제 운영 전환.
- 설치형 제품은 SDWT 데이터 범위를 표현할 수 있는지 개별 검토한다. SSO 연결만으로 이 정책이 적용됐다고 간주하지 않는다.
- 기존 사용자 변경을 보존한다. 커밋·push·운영 배포·실제 사용자 일괄 등록은 실행하지 않았다.

## 설계

### 1. 소속과 권한

```text
사용자 속성: user_sdwt_prod=SDWT-A, line_id=LINE-1

Keycloak Groups:
SDWT-A
  admin
  user
  viewer
SDWT-B
  admin
  user
  viewer
```

- SDWT 이름을 식별에 그대로 사용한다. 고정 SDWT ID와 별도 실제 소속 그룹은 만들지 않는다.
- 실제 소속은 `user_sdwt_prod`로 표시·소속별 알림에 사용한다. 여러 권한 그룹에서 실제 소속을 추정하지 않는다.
- SDWT는 전체 대상 목록에서 유일하고 하나의 line에 대응해야 한다. 이름 중복과 `/`가 포함된 이름은 도입 전 목록 검증에서 보고한다. 이름을 조용히 치환하거나 충돌하는 경로로 등록하지 않는다.
- 소속이 없으면 두 소속 claim을 생략하고 기본 그룹에 가입시키지 않는다. 명시적 타 SDWT 권한 부여는 가능하다.
- 권한 그룹에는 소속 속성이나 공통 `admin` 역할을 매핑하지 않는다. 그룹 속성 상속으로 실제 소속이 오염되지 않게 한다.
- 최초 등록 시 참조 테이블로 소속과 line을 저장하고 `/{본인SDWT}/user`에 가입한다. 이후 로그인에서 소속을 근거로 그룹을 자동 복구하지 않는다.
- 참조 테이블의 이후 변경은 사용자 소속을 덮어쓰지 않는다. 관리자가 소속을 수정해도 권한은 별도 가입·탈퇴 작업으로 관리한다.

### 2. 등급과 판정

| 그룹 | 공통 의미 |
| --- | --- |
| `/{SDWT}/viewer` | 해당 SDWT 데이터 조회 |
| `/{SDWT}/user` | 해당 SDWT의 일반 업무 사용, 조회 포함 |
| `/{SDWT}/admin` | 해당 SDWT의 업무 관리, 일반 사용·조회 포함 |

- 사용자별·SDWT별로 한 등급을 유지한다. Keycloak 자체의 배타적 가입 기능으로 가정하지 않는다.
- 중복 가입은 `admin > user > viewer`로 해석하고 무결성 점검에서 보고한다. 강등은 이전 상위 등급을 제거해야 완료된다.
- 부모 그룹만 가입하면 권한이 없다. SDWT를 모르는 경로, 알 수 없는 등급, 경로 깊이가 다른 그룹은 권한으로 해석하지 않는다.
- 그룹 claim 누락·빈 배열은 권한 없음이다. 잘못된 claim 타입을 문자열로 변환해 허용하지 않는다.
- `/headlamp-admins` 같은 다른 계약의 그룹은 무시한다. 부분 문자열이나 경로 접두사만으로 SDWT 권한을 부여하지 않는다.
- `admin`은 해당 SDWT 업무 관리자이며 Keycloak·서버·클러스터·앱 전역 관리자 권한이 아니다.
- 앱별 등급이나 앱별 접근 예외는 두지 않는다. 새로운 업무 앱도 같은 SDWT 등급을 적용하므로 앱 추가 자체가 기존 사용자 권한의 적용 대상 확대다.
- 목록·상세·수정·다운로드·검색에서 실제 자원의 SDWT와 요청자의 등급을 대조한다. 요청자가 넘긴 SDWT만 믿지 않는다.
- 서로 다른 SDWT의 등급은 독립적이다. A admin이 B viewer를 admin으로 승격시키지 않는다.
- 단일 SDWT 권한만으로 해당 line의 다른 SDWT까지 허용하지 않는다. line 전체 집계, 개인 자원, 공용 자원, 시스템 작업의 판정은 실제 자원 단위를 조사해 별도 명시한 뒤 해당 경로를 전환한다.

### 3. 토큰과 앱 계약

다음은 기존 신원 claim 중 일부와 새 권한을 함께 표현한 예시다. 발급자·audience·만료 등의 검증 필드를 생략한 것으로 실제 JWT 전체가 아니다.

```json
{
  "sub": "keycloak-user-id",
  "userid": "employee-epid",
  "user_sdwt_prod": "SDWT-A",
  "line_id": "LINE-1",
  "groups": ["/SDWT-A/admin", "/SDWT-B/viewer"]
}
```

- Group Membership mapper를 사용하고 `Full group path=true`, claim 이름은 `groups`, 값은 문자열 배열로 고정한다.
- 이 계약을 사용하는 앱에 공통 OIDC client scope를 연결한다. ID Token·Access Token·UserInfo 출력 계약을 맞추되 기존 `groups` mapper 중복을 먼저 조사한다.
- scope의 적용 대상은 명시적으로 관리한다. Headlamp 등의 기존 client scope·mapper를 일괄 교체하지 않는다.
- API Bearer 인증은 해당 API용 Access Token의 서명·issuer·audience·만료를 검증한다. ID Token을 임의의 API Bearer 토큰으로 받지 않는다.
- Portal은 검증한 OIDC 로그인과 서버 세션을 유지하되, 최신 그룹과 유효기간을 서버에서 관리한다. 브라우저가 보낸 임의 그룹 값을 저장하지 않는다.
- 목표 권한 반영 지연은 최대 5분이다. Access Token 수명 300초와 함께 Portal 세션의 권한 재검증·교체를 구현한다. 만료 뒤 갱신 실패 시 보호된 요청을 거부하며 옛 권한을 무기한 사용하지 않는다.
- Keycloak 갱신으로 그룹이 제거되면 Portal 복제본에서도 제거한다. 추가만 하는 동기화나 기존 로컬 권한과의 합집합은 사용하지 않는다.
- 권한 회수 즉시성을 로그아웃만으로 보장하지 않는다. 서버 세션 무효화와 API 토큰 수명을 각각 검증한다.
- Keycloak을 최종 소속·권한 원본으로 전환한 뒤 Portal은 읽기용 복제만 유지한다. 현재 Portal 원본에서 전환할 때의 값 비교·계정 연결을 별도로 수행한다.

### 4. 초기 일괄 등록과 기존 사용자

- 신규 Keycloak 등록 도구는 EPID→SDWT 목록과 SDWT→line 목록을 입력으로 받는다. 입력 파일 경로·비밀값은 env/명시 인자로 받는다.
- 기본 dry-run에서 중복 EPID, 알 수 없는 SDWT, SDWT의 복수 line 연결, 기존 계정 충돌을 보고한다.
- 신규 사용자에만 소속 저장과 본인 SDWT user 가입을 수행한다. 재실행으로 기존 사용자 소속·권한을 덮어쓰지 않는다.
- Keycloak Admin API는 여러 호출을 DB 트랜잭션으로 묶을 수 없으므로 부분 실패를 기록하고 재실행할 수 있어야 한다. 계정 생성 뒤 그룹 가입에 실패한 사용자를 일반적인 기존 계정 skip으로 방치하지 않는다.
- EPID username으로 사전 등록한 계정이 사내 broker 로그인 시 같은 계정에 연결되는지 검증한다. 이메일 일치만으로 계정을 무조건 연결하지 않는다.
- 기존 Portal 사용자 ID·업무 외래키를 보존한다. sabun·EPID·Keycloak subject의 불일치를 보고하고 중복 계정을 생성하지 않는다.
- 기존 권한은 삭제 전에 사용자×SDWT×앱×등급으로 내보낸다. 새 공통 등급과의 차이를 비교한다.
- 기존 앱별 등급이 다르면 하나의 공통 등급으로 완전히 동일하게 보존할 수 없다. 자동으로 최댓값을 모든 앱에 확장하지 않고 차이 목록에 표시하여 전환 전에 처리한다.
- 기존 권한 데이터는 검증과 복구를 위해 보관하되 전환 후 런타임 허용 조건으로 계속 합치지 않는다.

### 5. 운영 절차

- 권한 부여·회수: Keycloak 기본 UI에서 등급 하위 그룹에 가입·탈퇴한다. 앱의 SDWT admin에게 Keycloak 관리 권한을 자동 부여하지 않는다.
- 조직 이동: 소속 속성과 line 수정, 이전 SDWT 권한의 유지·회수 검토, 새 SDWT 권한 부여를 함께 기록한다.
- 이름 변경: 기존 부모 그룹을 rename하고 사용자 소속·참조 테이블·앱 저장값을 함께 갱신한다. 기존 그룹을 삭제·재생성하지 않는다.
- 이름 변경 동안 이전 토큰과 앱 캐시가 남는 것을 고려해 점검 시간 또는 기간 제한된 이전 이름 대응을 사용한다. 이전 이름을 다른 SDWT에 즉시 재사용하지 않는다.
- 조직 분할·통합: 단순 rename으로 처리하지 않고 사용자 권한·업무 데이터의 이전 대상을 검토한다.
- 감사: Keycloak 관리자 이벤트와 등록 도구의 변경 요약을 기록한다. 주기적으로 중복 등급·부모만 가입·알 수 없는 SDWT·퇴사자 권한을 점검한다.

## 실행 단계

- [x] P0. 최종 계약과 이전 계획 대체 관계를 문서에 반영한다.
- [x] P1. Keycloak 설정: 그룹 트리 준비 도구, 공통 groups mapper/scope, 명시적 client 연결, 300초 토큰 설정을 구현한다. API 실행 스크립트를 배포 원본으로 사용하고 기존 스택 YAML에는 그룹·사용자 정보를 넣지 않는다. 로컬 mock mapper 계약을 맞춘다.
- [x] P2a. 초기 등록: Keycloak 사전 등록·최초 user 가입·dry-run·부분 실패 재실행을 구현한다. 사용자 생성 요청에 속성·그룹을 함께 보내고 Portal 기존 등록 명령과 구분한다.
- [ ] P2b. 사내 broker 첫 로그인 연결을 실제 IdP 계약으로 검증한다. 비밀번호 없는 사전 등록 계정을 자동으로 연결할 수 있다고 가정하지 않는다.
- [ ] P3. 권한 수신: Portal auth/account 공개 facade에 그룹 해석·검증·읽기용 복제·세션 갱신을 구현한다. 기존 사용자 식별과 소속 claim을 연결한다.
- [ ] P4. 권한 소비: 실제 API별 데이터 단위와 viewer/user/admin 기능표를 작성한다. SDWT 경로부터 전환하고 line·개인·공용·시스템 경로는 범위별 검증 뒤 전환한다. 기존 권한 신청·부여 UI/API를 새 원본과 충돌하지 않도록 정리한다.
- [ ] P5. 이관 검증: 기존 실효 권한과 신규 공통 등급 차이를 dry-run으로 비교하고 해결한다. 테스트 계정으로 여러 앱의 동일 SDWT 권한과 5분 이내 회수를 재현한다.
- [ ] P6. 운영 전환: 백업·변경 동결·등록/이관·세션 갱신·회귀 확인 순서로 적용한다. 적용 실패 시 설정/데이터/앱 버전을 함께 복구하고 새로 회수한 권한이 부활하지 않는지 대조한다.

P1은 실제 권한 검사 전환이 아니다. P2–P5가 준비되기 전에 운영 그룹 정책으로 판정을 교체하지 않는다. 참조 파일·운영 연결 없이 실행할 수 있는 구현과 합성 데이터 검증을 먼저 완료한다.

## 검증

### 이번 문서 반영

- `make audit-docs`: 문서 inventory 검사.
- 새 계획의 필수 8개 섹션·JSON 예시·상대 링크 정적 확인.
- `git diff --check`: 공백 오류 검사.

### 후속 구현 완료 조건

- mapper API 회귀, 그룹 등록 멱등성·실패 재개, 로컬/운영 claim 일치 검증.
- `node --test apps/tooling/tests/environment.test.cjs` 및 영향받는 배포 검사.
- `make k8s-export`, `make server-check APP=keycloak PROFILE=prod`, `make k8s-render-local`. 실제 클러스터 적용 성공과 정적 검사를 구분한다.
- Docker Compose api에서 account/auth 및 변경한 업무 도메인 테스트·migration 검사를 실행한다. 소스 mount 또는 이미지 갱신을 명시한다.
- 그룹 없음·부모만 가입·잘못된 타입·알 수 없는 등급·다중 SDWT·중복 등급·강등·다른 SDWT 자원 접근·소속 없음·소속 변경을 검증한다.
- 로그인 후 그룹 제거, 갱신 실패, 오래된 Django 세션을 포함해 5분 이내 회수를 실제 Keycloak 26.7.1로 검증한다.
- 모든 앱에서 A admin/B viewer 조합을 교차 검증하고 목록·상세·다운로드·검색·수정 우회를 확인한다.
- 기존 Headlamp client·권한에 변화가 없는지 검증한다.
- 초기 사용자 broker 로그인, 이름 변경과 이전 토큰, 기존 사용자 권한 차이 보고서를 검증한다.
- 변경한 프론트엔드 검사 및 필요한 backend/frontend boundary·offsite 계약 검사를 실행한다.

## 위험과 대응

- 권한 단순화와 기존 앱별 권한의 완전 보존은 충돌할 수 있다. 실제 차이 목록을 만들고 자동 승격을 하지 않는다.
- 토큰 만료와 Django 세션 만료는 다르다. 갱신·검증 수명을 구현하지 않은 상태를 전환 완료로 표시하지 않는다.
- SDWT→line은 여러 SDWT→한 line일 수 있다. 단일 SDWT admin을 line 전체 admin으로 해석하지 않는다.
- 범위 없는 업무·전역 운영 설정은 SDWT 그룹만으로 의미가 정해지지 않는다. 관련 경로 조사와 판정표가 완료되기 전에는 임의 권한을 부여하지 않는다.
- 그룹명은 권한 식별자다. 이름 변경은 앱 데이터·캐시·토큰까지 포함한 운영 변경으로 관리한다.
- 다른 과거 계획의 미확정 항목과 완료 표시는 이 계획에 자동 승계하지 않는다.

## 진행 기록

- 2026-09-25: 사용자 요청으로 초기 등록 CSV를 사내 OIDC claim 이름에 맞춘다. `epid→userid`, `knox_id→loginid`, `email→mail`, `department→deptname`이며 `sabun`, `username`, `grdname_en`과 별도 소속 입력 `user_sdwt_prod`는 유지한다. Keycloak 저장 속성과 기존 사내 mapper 계약은 변경하지 않는다.
- 2026-09-25: CSV 명칭 통일 후 템플릿 입력부터 실제 Keycloak 속성 저장·기존 계정 충돌 검사를 포함한 15건이 통과했다. 예시 CSV 검사·Keycloak 서버 원본·diff 검사도 통과했다.

- 2026-09-25: 후속 정정으로 CSV의 `career_level`을 제거하고 `grd_name`을 기존 사내 OIDC 값인 `grdname_en`으로 변경한다. 초기 등록은 기존 `grdname_en` 속성을 사용하며 새 `career_level` 프로필 정의를 제거한다. 기존 사내 `grdName`의 별도 매핑은 변경하지 않는다.
- 2026-09-25: 정정 후 실제 Keycloak 저장·재등록 보존·빈 값 처리와 이전 CSV 헤더 거부를 포함한 14건, 환경 회귀 36건을 통과했다. 전달 YAML 재생성·서버 원본·diff 검사도 통과했다.

- 2026-09-25: 사용자 CSV에 선택 항목 `grd_name`, `career_level`을 추가한다. 템플릿·예시·입력 허용 목록·신규 사용자 속성 저장을 맞추고 `career_level`은 선택적 관리자 편집 User Profile 속성으로 정의한다. 기존 계정 보존과 기존 claim 계약은 유지한다.
- 2026-09-25: 두 선택 항목의 실제 Keycloak 저장·빈 값 생략·기존 값 보존을 포함한 14건, 환경 회귀 36건을 통과했다. 전달 YAML 재생성, Keycloak 서버 원본 및 diff 검사도 통과했다. 운영에는 적용하지 않았다.

- 2026-09-25: 사용자가 SDWT 이름을 유지하고 SDWT별 admin/user/viewer를 모든 앱에 공통 적용하는 하위 그룹 방식을 확정했다.
- 2026-09-25: 현재 mapper·Portal 로그인·권한 서비스·초기 등록 명령을 조사했다. 앱별 권한 이관과 세션 갱신이 필요함을 확인하고 P1–P6로 분리했다.
- 2026-09-25: 최종 설계를 문서에 반영했다. 실행 코드·DB·Keycloak 운영 설정은 이번 문서 작업에서 변경하지 않았다.
- 2026-09-25: 문서 검사에서 기존 작업 트리의 `register_reference_users` 명령이 inventory/operations 색인에 누락된 것을 발견해 Portal 전용 명령임을 명시하여 보완했다.
- 2026-09-25: 보완 후 `make audit-docs`, 필수 섹션·JSON·상대 링크 검사, `git diff --check`를 통과했다. 문서만 변경하여 업무 코드 테스트와 운영 토큰 검증은 실행하지 않았다.
- 2026-09-25: 사용자가 구현과 초기 설정 자동화를 요청했다. Python 표준 라이브러리 Admin API 스크립트, Make 진입점, 참조 CSV 예시와 운영 안내를 추가했다. realm 기본 그룹·기존 mapper·신원 충돌은 쓰기 전에 차단한다.
- 2026-09-25: 실제 Keycloak 26.7.1 기본 optional scope `microprofile-jwt`의 groups claim 충돌을 확인했다. 선택한 업무 client에서 이 optional 연결만 해제하며 다른 client·scope 자체는 보존한다.
- 2026-09-25: 전용 임시 Keycloak에서 신규 등록·반복 실행·소속 없음·기존 권한 회수 보존·실패 후 재실행·토큰 발급·그룹 제거 후 갱신을 검증했다. 사내 broker 로그인과 Portal Django 세션 갱신을 검증한 것으로 간주하지 않는다.
- 2026-09-25: 최종 검증은 실제 Keycloak 26.7.1을 포함한 스크립트 검사 12건, 환경·서버 선택 checkout 회귀 53건, 로컬 Kubernetes 렌더, Keycloak 서버 원본 검사, 문서 inventory와 diff 검사 모두 통과했다. 임시 컨테이너만 사용했고 운영 데이터는 변경하지 않았다.
- 2026-09-25: P4에 필요한 line 전체 데이터 권한은 사용자에게 확인 중이다. 단일 SDWT 권한을 line 전체 권한으로 확대하지 않고, 모든 대상 SDWT의 필요한 등급을 요구할지 또는 line 경로를 이번 전환에서 제외할지 답변을 기다린다. 초기 설정 도구와 이 정책 질문은 독립적이다.
- 2026-09-25: 사용자 요청으로 예시 데이터와 구분되는 헤더 전용 CSV 템플릿 두 개를 추가했다. 입력 스크립트로 템플릿에 합성 행을 채운 파일을 검증하고 diff 검사를 통과했다.
