# ExecPlan: Portal Keycloak 전환

## 목표
새 DB에서 EPID로 식별하고 Keycloak 인증·권한만 사용하는 Portal을 제공한다.
Etch 내부 deptid는 모든 활성 앱을 사용하고 외부 인원은 앱별 또는 전체 앱 역할을 받는다.
SDWT 데이터 권한은 별도 그룹 등급이며 portal-admin만 전체 접근한다.

## 현재 상태
Keycloak code+PKCE 구현과 ADFS 분기, DB 기반 부서·소속 권한이 공존한다.
시작 시 작업 트리는 깨끗하다. 기존 사용자 이관은 필요하지 않다.

## 범위
Portal API/Web, 연동 Keycloak client, 운영·로컬·테스트 env와 검사·문서.
사내 IdP, 다른 앱 인증, 서비스 간 전용 token API, 기존 migration 이력은 유지한다.

## 설계
- userid→avatarid(필수 고유 EPID), loginid→knox_id. 사번 자동 연결 없음.
- PORTAL_INTERNAL_DEPT_IDS는 정확히 비교하는 JSON 문자열 배열.
- portal-all-apps, 앱-user, 실제 관리 기능의 앱-admin, portal-admin 역할.
- /SDWT/viewer|user|admin 그룹. 본인 소속은 권한을 부여하지 않는다.
- 검증한 로그인 snapshot은 서버 세션별로 저장하고 요청 전용 사용자 객체에 연결한다.
  공개 facade는 명시적인 context도 받으며 DB 사용자만 있는 호출은 권한을 갖지 않는다.
  DB 잠금으로 사용자를 다시 조회하는 쓰기 호출은 원래 context를 명시적으로 전달한다.
- 다음 로그인까지 권한 유지. 전체 조직 목록 동기화와 Admin API 호출 없음.
- 관리자 비상 로그인은 업무 API 접근 권한이 없다.
- 변경 API는 410 managed_by_keycloak, 화면은 조회 전용.

## 실행 단계
- [x] 인증·EPID·세션 snapshot 및 새 migration
- [x] 공통 권한·업무 데이터 범위·종료 API
- [x] 조회 화면과 접근 안내
- [x] 운영·로컬 Keycloak·env·문서 동기화
- [x] 관련 회귀 테스트와 검증

## 검증
Compose api에서 auth/account 및 영향 업무 기능 테스트, 설정·migration 검사.
Web test/lint/build, 경계 검사, env·routing 검사, 서버 정적 검사.
준비된 로컬 환경에서는 로그인·권한 거부·로그아웃 검증.

## 위험과 대응
권한 context가 없는 호출은 실패 폐쇄한다. staff/DB grant는 우회 근거가 아니다.
조직 DB가 없어도 SDWT 문자열로 데이터 조회·쓰기를 판정한다.
권한 회수는 다음 로그인 정책이며 기존 세션은 만료까지 유지된다.
검증 도구가 없거나 환경이 준비되지 않으면 실행 불가 사유를 명시한다.

## 진행 기록
- 2026-09-25: 사용자 확정 계획을 기록하고 구현 시작. 자동 커밋·push·운영 배포 없음.

- 2026-09-25: EPID migration 0008, Keycloak 전용 code+PKCE/JWKS 인증, 세션별 앱·SDWT 권한을 구현했다. DB 권한·Django 관리자 플래그는 업무 접근 판정에서 제외했다.
- 2026-09-25: 기존 Portal 승인·소속 변경 API는 410으로 종료하고 계정 화면은 조회용으로 교체했다. 메일·Assistant는 조직 목록 없이 SDWT 문자열을 사용하며 전체 관리자의 직접 SDWT 선택을 지원한다.
- 2026-09-25: env·client 등록·로컬 realm·운영 문서를 함께 갱신했다. 자동 기본 관리자 생성과 개발 권한 seed를 제거했다. 과거 migration 테스트는 유지하고 폐기한 DB 권한·ADFS 테스트를 새 계약 테스트로 대체했다.

## 최종 검증 결과
- Docker Compose API 전체 **933개 통과**. 별도 Keycloak 26.7.1 컨테이너의 실제 code 교환·서명 검증·다섯 계정 유형·로그아웃 검증을 포함하며 skip 없음.
- 실제 Keycloak에서 client 등록 스크립트 최초 실행·재실행 성공. Keycloak 이미지에 없는 awk 의존성을 Bash로 교체했다.
- Django `check`, `makemigrations --check --dry-run` 통과. 신규 migration 외 누락 없음.
- Web **57개 파일 / 212개 테스트 통과**, lint·build 통과. 기존 대형 번들 경고는 남는다.
- 환경·Kubernetes routing·server checkout 도구 **61개 테스트 통과**.
- API/Web 경계, UI 일관성 검사와 `git diff --check` 통과.
- Portal·Keycloak `server-check`, 로컬 Portal·Keycloak Kustomize 렌더 통과.
- 임시 Keycloak·CI PostgreSQL은 검증 후 제거한다. 기존 로컬 realm·사용자 데이터는 삭제하지 않는다.

## 운영 적용에 필요한 입력
- 실제 Etch `deptid` 목록을 `deploy/portal/env/prod/api.env`의 `PORTAL_INTERNAL_DEPT_IDS`에 설정해야 한다. 현재 빈 배열은 의도적으로 배포 검사를 통과하지 못한다.
- 운영 URL·DB·client secret은 운영자가 준비한 env를 사용한다. 새 DB migration과 client 등록, 최초 `portal-admin` 지정 후 사내 broker의 실제 claim을 확인한다.
- 이번 작업에서는 운영 배포·커밋·push를 수행하지 않았다.
