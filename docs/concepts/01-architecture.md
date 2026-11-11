# 전체 아키텍처

[문서 홈](../README.md)

- [서비스 구성](#서비스-구성)
- [용어](#용어)

## 서비스 구성


Tailwind는 업무 화면을 제공하는 Portal과, 로그인·작업 실행·파일 저장을 담당하는 서비스를 함께 관리합니다.
Portal은 브라우저에서 실행되는 React 화면과 Django API로 구성됩니다.
메일·Assistant·설비 조회 등 업무 기능은 Portal 안에서 기능 단위로 나눠 개발합니다.

이 문서에서는 서비스 관계와 데이터 흐름을 먼저 설명합니다.
정확한 화면·API·모델 이름은 [구현 색인](../reference/02-inventory.md), 수정 규칙은 [개발 안내](../README.md#개발)에서 확인합니다.

### 구성 요소

| 구성 요소 | 하는 일 | 개발 PC에서의 실행 |
| --- | --- | --- |
| Portal Web | 업무 화면을 보여주고 사용자 입력을 API에 전달 | kind의 Web 또는 별도 Vite 개발 서버 |
| Portal API | 요청의 인증·권한을 검사하고 업무 데이터를 조회·변경 | kind의 Django API |
| Keycloak | 로그인과 앱 역할·SDWT 그룹 관리 | 로컬 Keycloak과 테스트 계정 |
| PostgreSQL | 사용자·업무 데이터·처리 이력 저장 | kind 밖의 별도 Docker 컨테이너 |
| MinIO | 메일 첨부·이미지 등 파일 저장·조회 | 로컬 객체 저장소 |
| Airflow | DAG에 정의된 수집·적재·요약·메일 작업 실행 | 로컬 Airflow가 Portal 공개 API 호출 |
| 외부 서비스 | RAG 검색·답변 생성·메일·Jira 등 연동 | 대부분 `local/adfs_dummy`가 대체 |
| FTP·Monitoring·Headlamp | 파일 수신, 지표 수집, Kubernetes 조회·관리 | 각 앱의 로컬 구성으로 실행 |

```mermaid
flowchart LR
    Browser[브라우저의 Portal 화면] -->|업무 API 요청| API[Django API]
    Browser -->|로그인| Keycloak[Keycloak]
    API -->|토큰 검증| Keycloak
    API --> DB[(PostgreSQL)]
    API --> Files[(MinIO·참고 파일)]
    API --> External[외부 서비스·로컬 mock]
    Airflow[Airflow 작업] -->|인증된 공개 API 호출| API
    FTP[FTP 수신 파일] --> Load[파일 적재 작업]
    API --> Load
    Load --> DB
```

로컬 전체 환경은 한 PC에서 동작합니다. `make dev`로 앱을 실행하고,
기동 도구는 별도 Job으로 DB migration과 개발 데이터 준비를 수행합니다.
설정·계정·영속 데이터는 [로컬 안내](../../local/README.md)를 기준으로 확인합니다.

### 앱 소유 경로

하나의 앱에 필요한 파일을 세 영역에서 관리합니다. 예를 들어 Portal 화면을 바꾸는 코드는
`apps/portal/web`, 서버 설치 입력은 `deploy/portal`, 개발 PC 전용 설정은 `local/portal`에 있습니다.

| 영역 | 책임 | 시작점 |
| --- | --- | --- |
| `apps/<app>` | 직접 개발하는 소스·이미지·검사 도구 | [Portal](../../apps/portal/README.md), [Airflow](../../apps/airflow/README.md) |
| `deploy/<app>` | 서버 배포·공통 정의·CI 입력 | [서버 배포 안내](../../deploy/README.md) |
| `local/<app>` | 개발 PC의 차이·mock·실행 도구 | [로컬 실행 안내](../../local/README.md) |

공통 정의를 `deploy`에 두고 `local`에서 재사용합니다. 앱 목록과 서버 검사 그룹의 원본은 `deploy/shared/apps.json`입니다.
서버 검사·배포 도구는 준비된 이미지와 `deploy`의 배포 파일만 사용하며 `local`에 의존하지 않습니다.

### 요청 흐름

메일 목록을 여는 경우를 예로 들면 다음 순서로 동작합니다.

1. 브라우저가 메일 화면을 표시하고, 해당 기능의 hook이 조회를 요청합니다.
2. API client가 `/api/v1/**` 경로로 Django API를 호출합니다.
3. View가 로그인·앱 접근·입력을 확인하고 업무 계층을 호출합니다.
4. 조회는 selector, 쓰기·트랜잭션·외부 호출은 service가 담당합니다.
5. DB·파일·외부 서비스에서 얻은 결과를 API가 반환하고 화면은 React Query의 조회 결과로 표시합니다.

서버에서 온 데이터를 UI 상태 저장소에 다시 복제하지 않습니다. 필터 패널 열기·선택 행 등 화면 조작 상태만
컴포넌트나 기능 내부 Zustand에 보관합니다. [Web 개발](../development/01-frontend.md)과 [API 개발](../development/02-backend.md)에서 세부 책임을 확인합니다.

### 핵심 데이터 흐름

#### 인증과 소속

사용자는 Keycloak으로 로그인합니다. API가 로그인 토큰을 검증하고 EPID 사용자 정보를 갱신한 뒤,
검증된 앱 역할·SDWT 그룹을 로그인 세션에 저장합니다.
앱을 열 수 있는 권한과 해당 앱에서 조회·수정할 데이터 범위는 별도로 검사합니다.
역할·그룹 변경은 재로그인 후 반영됩니다. 기존 DB 소속·권한 테이블과 Django 관리자 플래그는 로그인 권한의 원천이 아닙니다.
세부 규칙은 [Auth](../features/01-auth.md#기능과-흐름)와 [Account](../features/02-account.md#기능과-흐름)를 확인합니다.

#### 메일과 RAG

Emails가 POP3 또는 Mail API로 메일을 수집하고, 메일함·세션 권한에 따라 접근 범위를 제한합니다.
첨부·이미지는 MinIO에 저장합니다. 검색 자료 등록·삭제가 필요하면 DB의 `EmailOutbox`에 작업을 쌓고,
별도 처리기가 RAG 서비스에 전달합니다. Assistant는 검색 결과를 답변 생성의 근거로 사용합니다.
[Emails](../features/03-emails.md#기능과-흐름)와 [Assistant](../features/04-assistant.md#기능과-흐름)에서 세부 흐름을 확인합니다.

#### Drone SOP 알림

메일 수집이나 Airflow 호출로 작업을 시작하고, 대상 line·소속·채널·수신자·전송 규칙을 계산합니다.
Jira·Messenger·Mail 채널별 실행과 전달 결과를 DB에 기록합니다.
Line Dashboard는 SOP 상태·이력·알림 설정을 조회·수정합니다.
[Line Dashboard / Drone](../features/05-line-dashboard.md#기능과-흐름)에서 설정과 발송 결과의 관계를 확인합니다.

#### 파일 적재와 Observer 조회

FTP 등으로 수신한 완료 파일을 Data Movement가 읽어 PostgreSQL 테이블로 적재합니다.
Observer는 line·SDWT·공정·설비 조건에 맞는 기준정보와 로그를 기본 DB에서 읽습니다.
API가 EQP·TIP·CTTTM·RACB·Drone 등의 로그를 공통 형태로 반환하면 화면이 타임라인과 상세 패널에 표시합니다.
[Data Movement](../features/13-data-movement.md#기능과-흐름)와 [Observer](../features/06-observer.md#기능과-흐름)에서 처리 순서와 원천 시간 해석을 확인합니다.

### 경계 규칙

코드의 기능 경계는 내부 구현을 서로 직접 참조하지 않도록 유지합니다.
Web은 feature의 `index.js` 공개 진입점을, API는 selector 또는 service facade를 사용합니다.
Web의 허용된 기능 간 의존 방향과 API 계층별 책임은 각각 [Web 개발](../development/01-frontend.md#feature-경계),
[API 개발](../development/02-backend.md#책임-분리)에 정리되어 있습니다.

외부 URL과 인증값은 env로 주입합니다. 사내 서비스 연결을 바꾸면 개발 PC의 대응 설정·mock도 함께 확인합니다.
[외부 연동](03-integrations.md)에는 서비스별 역할과 확인할 계약이 있습니다.

### 상세 색인

- 데이터가 남는 위치와 모델 관계: [데이터 모델과 저장소](02-data-model.md)
- 개별 기능의 화면·권한·처리 흐름: [기능 안내](../features/README.md#기능-찾기)
- 요청·응답·인증·오류: [API 명세](../features/README.md#공통-api-호출-규칙)
- 실제 경로·설정·관리 명령: [참고 자료](../README.md#설정명령)

## 용어


문서에 자주 등장하는 기술 용어와 이 프로젝트에서의 쓰임을 설명합니다.
업무 약어의 정확한 의미는 해당 기능 문서에서 확인하며 임의로 풀어 쓰지 않습니다.

### 코드와 요청 처리

| 용어 | 의미와 이 프로젝트에서의 쓰임 |
| --- | --- |
| Portal | React 화면과 Django API로 구성한 업무 포털 |
| feature / 도메인 app | 메일·계정처럼 하나의 업무 기능을 묶은 코드 단위. Web은 feature, API는 Django app으로 구성 |
| route / endpoint | route는 화면 또는 요청을 연결하는 경로, endpoint는 HTTP method와 경로로 구분하는 API 호출 지점 |
| facade | 기능 외부에 공개하는 진입점. 다른 기능은 내부 파일 대신 이 진입점을 사용 |
| view | 인증·입력·호출·응답 등 HTTP 요청 처리를 담당하는 API 계층 |
| selector | DB 등의 데이터를 읽는 계층. 조회 과정에서 데이터를 변경하지 않음 |
| service | 데이터 쓰기·트랜잭션·외부 호출 등 업무 처리를 담당하는 계층 |
| React Query | 서버에서 받은 데이터를 조회·캐시하고 변경 후 갱신하는 도구 |
| Zustand | 화면 선택·패널 상태 등 UI 상태를 보관하는 도구 |
| migration | DB 테이블·필드·데이터를 코드 버전에 맞게 바꾸는 절차 |

### 로그인과 외부 연동

| 용어 | 의미와 이 프로젝트에서의 쓰임 |
| --- | --- |
| Keycloak / OIDC | Keycloak은 로그인·역할·그룹 관리 서비스이며 OIDC는 로그인 신원을 전달하는 규격 |
| claim | 로그인 토큰에 포함된 신원·역할·그룹 정보. API가 검증한 뒤 세션에 저장 |
| session | 로그인 후 브라우저 요청을 사용자와 연결하는 서버 상태. 브라우저는 세션 쿠키를 사용 |
| scope / SDWT 등급 | scope는 앱 접근 범위, SDWT 등급은 해당 업무 데이터의 조회·쓰기·삭제 범위. 두 권한을 별도 검사 |
| EPID | 이 프로젝트의 로그인 사용자 식별값. 로컬에서는 테스트 계정 번호로 확인 |
| PKCE / JWKS | PKCE는 로그인 code 교환 검증, JWKS는 토큰 서명 검증에 사용하는 공개키 정보 |
| RAG / LLM | RAG는 질문과 관련된 자료를 찾아 답변 근거로 제공하는 방식, LLM은 답변을 생성하는 언어 모델 |
| mock / dummy 외부계 | 실제 사내 서비스를 대신하는 개발용 서버. `local/adfs_dummy`가 외부 로그인·RAG·LLM·메일·Jira 등을 대체 |
| Outbox | 외부 전달이 필요한 작업을 DB에 보관하고 별도 처리기가 전송하는 구조. 메일의 RAG 등록·삭제에 사용 |
| SSE | 서버가 응답을 이벤트 단위로 계속 보내는 HTTP 방식. Assistant 답변 스트리밍에 사용 |

### 실행 환경과 데이터

| 용어 | 의미와 이 프로젝트에서의 쓰임 |
| --- | --- |
| image / container | image는 실행할 소스·의존성 묶음, container는 그 image를 실행한 단위. 소스 변경 후 image 갱신 필요 |
| Kubernetes / kind | Kubernetes는 컨테이너 배포·실행 관리 도구, kind는 Docker 컨테이너로 개발용 Kubernetes 노드를 만드는 도구 |
| cluster / node / Pod | cluster는 실행 환경 전체, node는 실행 자원을 제공하는 단위, Pod는 컨테이너를 실행하는 Kubernetes 단위 |
| manifest / Kustomize overlay | manifest는 Kubernetes 자원 정의, overlay는 공통 정의에 환경별 차이를 적용하는 구성 |
| Helm / chart | Helm은 Kubernetes 배포 도구, chart는 해당 도구가 설치하는 자원·설정 묶음 |
| Ingress / TLS / VIP | Ingress는 외부 HTTP 요청 연결 규칙, TLS는 HTTPS 암호화, VIP는 서비스 진입점으로 사용하는 가상 IP |
| Secret / env | Secret은 Kubernetes 설정·인증값 전달 자원, env는 실행 프로세스에 전달하는 환경변수 |
| volume / PVC | volume은 컨테이너가 쓰는 저장공간, PVC는 Kubernetes에서 영속 저장공간을 요청하는 자원 |
| MinIO / Parquet | MinIO는 파일을 객체로 저장하는 서비스, Parquet은 분석용 참고 데이터를 저장하는 파일 형식 |
| Airflow / DAG | Airflow는 정해진 작업을 실행·관리하는 서비스, DAG는 실행할 작업과 선후 관계를 나타내는 정의 |
| smoke 검사 | 로그인·메일 등 대표 기능을 연결해 동작을 확인하는 통합 검사. 테스트 데이터·실행 이력이 생성될 수 있음 |
