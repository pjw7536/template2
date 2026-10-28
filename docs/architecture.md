# 전체 아키텍처

이 앱은 React SPA와 Django API가 한 저장소에 있는 업무용 모듈형 모놀리스입니다. 로컬 개발에서는 Keycloak으로 인증하고 dummy 외부계로 RAG, LLM, Mail, Jira를 대체합니다.

## 구성 요소

| 영역 | 경로 | 역할 | 상세 문서 |
| --- | --- | --- | --- |
| Web | `apps/portal/web` | React 19 + Vite SPA | [프론트엔드 상세 구조](frontend.md) |
| API | `apps/portal/api` | Django 5.2 이상·6.0 미만 API 서버 | [백엔드 상세 구조](backend.md) |
| Dummy 외부계 | `local/adfs_dummy` | 로컬 RAG/LLM/Mail/Jira 대체 서버 | [외부 연동 계약](integrations.md) |
| Env | `local/<app>/env`, `deploy/<app>/env` | 개발/운영 환경 변수 | [환경 설정](configuration.md) |
| Proxy | `deploy/portal/k8s/base/nginx.conf` | 로컬/운영 통합 진입점 | [운영/개발 명령](operations.md) |
| Docs | `docs` | 앱 상세 설명과 검증 기준 | [프로젝트 문서 홈](README.md) |

## 앱 소유 경로

소스·이미지는 `apps/<app>`, 배포·공통 정의는 `deploy/<app>`, 외부 PC 설정은 `local/<app>`에서 관리합니다.
Portal은 `apps/portal/api`와 `apps/portal/web`, Airflow는 `apps/airflow`가 소유합니다.
업무 feature 경계와 Python package 이름은 그대로 유지합니다. 앱 목록은 `deploy/shared/apps.json`입니다.
서버 배포는 준비된 이미지와 배포 파일만 필요하며 빌드 때만 `--with-source`로 소스를 추가합니다.
전체 시작점은 [Portal](../apps/portal/README.md), [Airflow](../apps/airflow/README.md)입니다.

## 요청 흐름

1. 브라우저가 React SPA route를 렌더링합니다.
2. 화면은 feature-local hook/API client를 통해 `/api/v1/**` Django endpoint를 호출합니다.
3. Django view는 인증, 요청 파싱, 응답 변환을 담당합니다.
4. 읽기 로직은 selector, 쓰기/외부 호출/transaction은 service가 담당합니다.
5. 데이터는 기본 PostgreSQL, MinIO, 외부 시스템 또는 dummy 외부계에서 조회/저장됩니다.

## 백엔드 모듈

| Django app | 역할 | 주요 저장소/연동 |
| --- | --- | --- |
| `api.auth` | OIDC 로그인/로그아웃/현재 사용자 | Keycloak OIDC, `api.account.User` |
| `api.account` | 세션 소속·권한 조회, 사용자 pool | Keycloak 세션, 기본 DB |
| `api.emails` | 메일 수집/조회/이동/삭제/OCR/RAG Outbox | 기본 DB, POP3, RAG, MinIO |
| `api.assistant` | 사용자별 대화방 저장과 화면별 AI 채팅 | PostgreSQL, OpenWebUI, RAG, LLM |
| `api.rag` | 외부 RAG 서버 공통 client | RAG |
| `api.drone` | Line Dashboard와 Drone SOP 알림 | 기본 DB, POP3, Jira, Mail API, Messenger |
| `api.observer` | 기본 DB 기준정보/로그 조회 | data movement 테이블, Drone 데이터 |
| `api.appstore` | 내부 앱 등록/댓글/좋아요 | 기본 DB, cover image |
| `api.voc` | VOC 게시판 | 기본 DB |
| `api.activity` | 활동 로그·앱 접속 통계·외부 사용량 동기화 | 기본 DB, 외부 사용량 API |
| `api.data_movement` | 파일 적재·CTTTM 요약 trigger | 기본 DB, FTP 수신 큐, OpenWebUI |
| `api.l3_spider` | 이상감지 조회·메일 규칙 | 기본 DB 인덱스, Parquet, Mail API |
| `api.l0_spider`, `api.pm_comparison`, `api.tttm_spider` | Spider 분석 데이터 조회 | Parquet·참조 파일 |
| `api.health` | 헬스 체크 | runtime 상태 |
| `api.common` | 공통 middleware/helper/client | logging, storage, mail, messenger |

## 프론트엔드 모듈

프론트엔드는 `apps/portal/web/src/features/<feature>` 단위로 구성됩니다. feature 외부 공개는 항상 `index.js` facade를 통합니다.

| Feature | 역할 | 주요 route |
| --- | --- | --- |
| `auth` | Keycloak 로그인, 세션 조회 | `/login` |
| `account` | 세션 계정·권한 조회, Portal 관리자 사용자 목록 | `/settings/account`, `/settings/members`, `/settings/permissions` |
| `emails` | 메일함과 메일 처리 | `/emails/inbox`, `/emails/sent`, `/emails/members` |
| `assistant` | RAG 기반 채팅 | `/assistant` |
| `line-dashboard` | Drone SOP/라인 대시보드 | `/ESOP_Dashboard/**` |
| `spider` | Spider 허브 | `/spider`, `/spider/defect` |
| `l0-spider`, `l1-spider`, `l3-spider` | L0·L1·L3 분석 화면 | `/spider/l0`, `/spider/l1`, `/l0_spider/**`, `/l3_spider`, `/spider/l3` |
| `pm-spider`, `tttm-spider` | PM·TTTM 분석 화면 | `/pm_spider`, `/spider/tttm`, `/tttm_spider` |
| `access-stats` | 앱 접속 통계 | `/access-stats` |
| `observer` | 설비/로그 Observer | `/observer`, `/observer/:eqpId` |
| `appstore` | 내부 앱 공유 | `/appstore` |
| `voc` | VOC 게시판 | `/voc` |
| `home` | 인증 후 홈 shell | `/` |
| `errors` | route error와 404 | `*` |
| `teamstaff` | 팀/인력 보조 화면 | `/teamstaff` |

## 핵심 데이터 흐름

### 인증과 소속

1. 사용자가 OIDC로 로그인합니다.
2. `api.auth`가 OIDC claim을 검증하고 `api.account.User`를 만들거나 갱신합니다.
3. `api.account`가 검증된 Keycloak 세션의 소속·앱 역할·SDWT 그룹으로 접근 범위를 계산합니다.
4. Emails, Assistant, Drone은 소속/권한 범위를 재사용해 조회와 작업 권한을 제한합니다.

### 메일과 RAG

1. Emails가 POP3 또는 Mail API에서 메일과 asset을 수집합니다.
2. 로그인 세션의 앱 역할·SDWT 등급과 mailbox 기준으로 메일 접근 범위를 계산합니다.
3. RAG 등록/삭제가 필요하면 `EmailOutbox`에 작업을 쌓습니다.
4. Outbox 처리기가 RAG insert/delete endpoint를 호출합니다.
5. Assistant는 RAG 검색 결과를 LLM에 전달해 답변을 생성합니다.

### Drone SOP 알림

1. Drone이 SOP 메일을 수집하거나 Airflow trigger로 pipeline을 시작합니다.
2. 대상 소속, line, channel, recipient, need-to-send rule을 계산합니다.
3. Jira, Messenger, Mail 채널별 dispatch와 delivery 상태를 저장합니다.
4. Line Dashboard 화면은 SOP 상태, 이력, 알림 설정을 조회/수정합니다.

### Observer 조회

1. Observer 화면이 line, SDWT, 공정, 설비 조건을 선택합니다.
2. API가 query를 정규화하고 기본 DB의 기준정보/로그 테이블을 조회합니다.
3. EQP, TIP, CTTTM, RACB, Drone 로그를 공통 observer item 형태로 반환합니다.
4. 프론트는 vis-timeline과 상세 패널에 변환된 로그를 표시합니다.

## 경계 규칙

- 프론트 feature 외부 공개는 `apps/portal/web/src/features/<feature>/index.js`를 통합니다.
- 프론트 feature 간 import는 public facade만 사용하며 선언된 `auth -> account`, `emails -> account`, `line-dashboard -> account` 방향만 허용합니다.
- 그 밖의 feature 조립은 `apps/portal/web/src/routes`, `apps/portal/web/src/components/layout`, `apps/portal/web/src/components/common`, `apps/portal/web/src/lib` 같은 non-feature 계층에서 수행합니다.
- `apps/portal/web/src/lib`는 app-shell context, framework adapter, 범용 helper만 소유합니다.
- React Query는 서버 데이터의 기준이고, Zustand는 feature-local UI 상태만 저장합니다.
- 백엔드 view는 HTTP 처리만 맡고, 비즈니스 로직은 service/selector에 둡니다.
- selector는 읽기 전용, service는 쓰기/transaction/외부 호출을 담당합니다.
- 다른 백엔드 feature 의존은 selector 또는 `services/__init__.py` facade를 사용합니다.
- backend service/selector package facade는 명시적 re-export만 포함합니다.
- 외부 시스템 URL과 인증값은 환경 변수로 관리합니다.

## 상세 색인

- 실제 route/model/env/command 목록: `docs/inventory.md`
- API 호출 규칙: `docs/api/README.md`
- 데이터 모델: `docs/data-model.md`
- 환경 설정: `docs/configuration.md`
- 운영 명령: `docs/operations.md`

Portal은 EPID 계정과 로그인 세션별 앱·SDWT 권한을 사용합니다. 앱 접근은 Keycloak client 역할만으로 허용하며 데이터 접근은 그룹 등급을 별도로 검사합니다. DB 소속·권한 테이블은 로그인 권한의 원천이 아닙니다.
