# 프로젝트 문서 홈

이 폴더는 Portal의 기능·구조·API와 개발·운영 방법을 설명합니다.
처음에는 아래에서 목적에 맞는 문서를 고르고, 구현 경로나 설정 이름이 필요할 때 상세 색인을 확인하세요.

## 목적별 시작점

| 하려는 일 | 먼저 읽을 문서 |
| --- | --- |
| 내 PC에서 실행하기 | [사용방법](usage.md) → [로컬 환경 준비](../local/README.md) |
| 서버에 배포하기 | [서버 배포 안내](../deploy/README.md) |
| 화면과 업무 기능 이해하기 | [모듈별 기능 안내](modules/README.md) |
| API 호출하기 | [API 공통 규칙](api/README.md) → 해당 모듈 API |
| 구조를 이해하고 개발하기 | [전체 아키텍처](architecture.md) → [프론트엔드](frontend.md) / [백엔드](backend.md) |
| 설정·외부 연결 점검하기 | [환경 설정](configuration.md), [외부 연동](integrations.md) |
| 오류를 점검하거나 관리 명령 실행하기 | [운영·개발 명령](operations.md) |
| AI 작업 지침·변경 근거 찾기 | [에이전트 문서](agent/README.md) |

## 실행 진입 안내

- [서버 Kubernetes 배포 문서](../deploy/README.md): 입문 가이드·서버 준비·앱별 배포·운영
- [사용방법](usage.md): Makefile 기반 개발·서버 실행
- [Migration 안내](migration-guide.md): 기존 migration 운영 절차 참고
- [로컬 Kubernetes 실행](../local/README.md)
- [저장소 검사 도구](../apps/tooling/README.md)

## 먼저 읽는 순서

전체 구조를 처음 살펴본다면 [아키텍처](architecture.md), [모듈별 기능](modules/README.md),
담당 영역의 [프론트엔드](frontend.md) 또는 [백엔드 구조](backend.md)를 먼저 읽으세요.
[인벤토리](inventory.md)는 실제 경로·모델·설정 이름을 찾을 때 사용하는 참고용 색인입니다.

## 문서 배치 기준

- `docs/`: 앱을 가로지르는 구조·설정·운영 설명
- `docs/modules/`: 화면과 업무 흐름, 권한, 운영 시 확인할 사항
- `docs/api/`: 요청·응답·오류 등 API 호출 계약
- `docs/integrations/`, `docs/k8s/`: 외부 저장소 참고표와 Kubernetes 명령어 참고
- `docs/agent/`: 에이전트 작업 지침과 과거 계획·결정 이력
- `apps/<app>/README.md`, `deploy/<app>/README.md`, `local/README.md`: 각 영역의 소스 개발·서버 배포·로컬 실행 안내

## 문서 지도

| 문서 | 설명 |
| --- | --- |
| [전체 아키텍처](architecture.md) | 전체 앱 구조, 모듈 경계, 핵심 데이터 흐름 |
| [앱 인벤토리](inventory.md) | 실제 API·화면 경로, 모델, 명령, 환경 변수 색인 |
| [프론트엔드](frontend.md) | React SPA 구조, 화면 경로, feature 공개 진입점, 상태 관리 원칙 |
| [백엔드](backend.md) | Django app 구조, view/selector/service 책임, URL prefix, 명령 |
| [데이터 모델](data-model.md) | 주요 DB 모델과 저장소 |
| [환경 설정](configuration.md) | env 파일, 설정 그룹, 로컬·운영 차이 |
| [API 문서](api/README.md) | 공통 호출 규칙과 모듈별 API 계약 |
| [모듈 문서](modules/README.md) | 모듈별 기능, 권한, 화면, 데이터, 동작 흐름 |
| [운영·개발 명령](operations.md) | 로컬 실행, 테스트, 관리 명령, 점검 절차 |
| [외부 연동](integrations.md) | Keycloak/OIDC, RAG, LLM, Mail, Jira, Messenger, MinIO, Airflow 연동 |
| [Kubernetes 명령어](k8s/README.md) | 상태·로그 조회와 리소스 관리 명령 참고 |
| [에이전트 문서](agent/README.md) | AI 작업 지침, 실행 계획, 결정 이력 |

## 모듈 목록

| 모듈 | 기능 문서 | API 문서 | 주요 화면/route |
| --- | --- | --- | --- |
| Auth | [Auth 모듈](modules/auth.md) | [Auth API](api/auth.md) | `/login`, OIDC callback |
| Account | [Account 모듈](modules/account.md) | [Account API](api/account.md) | `/settings/account`, `/settings/members` |
| Emails | [Emails 모듈](modules/emails.md) | [Emails API](api/emails.md) | `/emails/inbox`, `/emails/sent`, `/emails/members` |
| Assistant/RAG | [Assistant / OpenWebUI / RAG 모듈](modules/assistant.md) | [Assistant API](api/assistant.md) | `/assistant` |
| Line Dashboard/Drone | [Line Dashboard / Drone 모듈](modules/line-dashboard.md) | [Line Dashboard / Drone API](api/line-dashboard.md) | `/ESOP_Dashboard/**` |
| L3 Spider | [L3 Spider 모듈](modules/l3-spider.md) | [L3 Spider API](api/l3-spider.md) | `/l3_spider`, `/spider/l3` |
| L0 Spider | [앱 인벤토리](inventory.md) | [L0 Spider API](api/l0-spider.md) | `/l0_spider/**`, `/spider/l0` |
| PM SPIDER | [PM SPIDER 대시보드 데이터 연동 명세](modules/pm-comparison-dashboard-spec.md) | [PM SPIDER API](api/pm-spider.md) | `/pm_spider` |
| TTTM Spider | [앱 인벤토리](inventory.md) | [TTTM Spider API](api/tttm-spider.md) | `/spider/tttm`, `/tttm_spider` |
| Data Movement | [Data Movement 모듈](modules/data-movement.md) | [Data Movement API](api/data-movement.md) | 내부 API |
| Observer | [Observer 모듈](modules/observer.md) | [Observer API](api/observer.md) | `/observer`, `/observer/:eqpId` |
| AppStore | [AppStore 모듈](modules/appstore.md) | [AppStore API](api/appstore.md) | `/appstore` |
| VOC | [VOC 모듈](modules/voc.md) | [VOC API](api/voc.md) | `/voc` |
| Activity/Health | [Activity / Health 모듈](modules/activity-health.md) | [Activity / Health API](api/activity-health.md) | API only |

## 문서 완성 기준

- 신규 사용자가 `docs/README.md`에서 시작해 앱 실행, 화면 구조, API 호출, 데이터 흐름, 운영 점검까지 추적할 수 있어야 합니다.
- 각 feature는 “화면 route → frontend API client/hook → backend endpoint → selector/service/model → 외부 연동 또는 DB” 흐름으로 추적 가능해야 합니다.
- API 문서는 method, path, auth, query/body, response, error, side effect를 설명해야 합니다.
- 모듈 문서는 목적, 권한, 주요 상태, 동작 흐름, 운영 포인트, 관련 코드 경로를 포함해야 합니다.
- route/model/env/command 같은 변경 가능성이 큰 항목은 `docs/inventory.md`와 검증 스크립트로 drift를 줄입니다.

## 문서 작성 원칙

- 코드 동작과 다른 내용을 문서에 쓰지 않습니다.
- 내부 파일 경로는 설명을 보강하는 색인으로 사용하고, 업무 개념 설명을 먼저 둡니다.
- 외부 URL, token, credential은 env 이름과 역할만 문서화하고 실제 비밀값을 반복 기재하지 않습니다.
- 새 API나 route를 추가하면 `docs/inventory.md`, 해당 `docs/api/*.md`, 해당 `docs/modules/*.md`를 함께 갱신합니다.

## 과거 작업 기록

[에이전트 문서](agent/README.md)에서 작업 당시의 계획·검증·결정 이력을 찾을 수 있습니다.
완료된 기록의 경로와 명령은 이후 변경됐을 수 있으므로 현재 실행에는 위 운영·API 문서를 사용합니다.
