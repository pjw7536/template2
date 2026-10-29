# 용어 안내

[개념 안내](README.md) · [문서 홈](../README.md)

문서에 자주 등장하는 기술 용어와 이 프로젝트에서의 쓰임을 설명합니다.
업무 약어의 정확한 의미는 해당 기능 문서에서 확인하며 임의로 풀어 쓰지 않습니다.

## 코드와 요청 처리

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

## 로그인과 외부 연동

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

## 실행 환경과 데이터

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
| 선택 checkout | 서버에서 담당 앱의 배포 파일과 공통 파일만 내려받는 방식. 기본적으로 앱 소스·local·루트 docs를 제외 |
