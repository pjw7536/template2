# ExecPlan: 로컬 개발과 사내 배포 분리

## 목표
- 외부 PC 전용 설정·mock·kind·실행 도구를 `local/`에 모은다.
- 사내 서버는 앱별 sparse checkout을 사용하고 `local/` 없이 검사·렌더링한다.

## 현재 상태
- 배포 파일은 `deploy/<app>/`로 통합되어 있으나 로컬 파일이 섞여 있다.
- 전체 env 검사와 k8s-render가 로컬 파일을 요구한다.
- 기존 사용자 변경과 이전 작업을 유지하며 index는 수정하지 않는다.

## 범위
- 로컬 파일 이동, 경로 참조·검사·Makefile·운영 문서·규칙·회귀 테스트.
- 실제 앱 업무 로직, 인증 계약, DB, 사내 클러스터, commit/push는 변경하지 않는다.

## 설계
- local/portal에는 env·Compose·K8s overlay·Nginx·실행 도구, local/airflow에는 로컬 env·override·단독 구성을 둔다.
- local/adfs_dummy에 mock 소스를 이동하고 local/shared에 kind·로컬 인프라 조합을 둔다. L3 Spider mock 데이터 생성 도구도 local/portal/scripts/mock_data로 이동하고 기존 데이터 출력 위치를 유지한다.
- 공통 배포 정의는 deploy에 한 번만 두며 local이 참조한다. oidc/prod/CI test는 local로 이동하지 않는다.
- env 구조 검사는 앱·환경을 지정할 수 있게 하고 server-check는 실제 credential 없이 선택 앱의 원본을 검사한다. 실제값 검사는 기존 env-check가 담당한다.
- 서버 sparse checkout은 local을 제외한 앱·공통 도구·필요 소스를 선택하며 현재 개발 checkout에는 적용하지 않는다.

## 실행 단계
- [x] 현재 env·Compose·Kustomize·index 기준과 파일 스냅샷을 확보한다.
- [x] 로컬 파일을 이동하고 공통 참조를 수정한다.
- [x] 앱별 서버 검사와 선택 체크아웃 절차를 구현한다.
- [x] local 없는 격리 checkout 및 기존 로컬 구성의 회귀 검증을 수행한다.
- [x] 문서·규칙·검증 결과를 동기화한다.

## 검증
- 이동 전후 env 내용·권한, Compose 최종 구성, Kustomize 결과, local API 합성 비교.
- 기존 env/라우팅 테스트와 새 서버 선택 체크아웃·검사 테스트.
- env-profile-key-check, k8s-render/export, server-check 앱별 실행.
- agent 테스트·문서 감사, Shell 문법, 문서 링크, git diff --check.

## 위험과 대응
- 상대 경로 변경: 최종 구성·마운트 비교로 검증한다.
- 서버 도구의 local 의존: local이 없는 임시 저장소에서 실제 sparse checkout과 검사를 수행한다.
- 기존 설정·사용자 작업 손실: 파일 내용·권한과 index 항목을 보존하고 실제 배포하지 않는다.

## 진행 기록
- 2026-09-14: 사용자가 local/deploy 분리와 사내 선택 체크아웃 도입을 승인했다.

- 2026-09-14: local/portal·airflow·adfs_dummy·shared로 외부 PC 전용 파일을 이동하고 루트 개발 진입점을 유지했다. 공통 Portal K8s·Airflow Compose는 원본을 재사용한다.
- 2026-09-14: env 검사를 앱·환경별로 선택할 수 있게 했고 server-check 및 안전한 서버 sparse checkout 도구·문서를 추가했다. 실제값 검사와 원본 검사를 구별했다.
- 2026-09-14: 공개 원본·가짜 env로 만든 임시 Git 저장소에서 네 앱을 각각 sparse clone/checkout했다. local 및 다른 앱이 없는 상태에서 prod/oidc 검사와 Keycloak export가 통과했다. 수정 파일·미지원 입력·누락 예시 실패 경로도 검증했다.
- 2026-09-14: Compose 6개 runtime 구성과 Kustomize 6개 출력, 로컬 API 합성 env, env 내용·권한, dummy 소스가 동일했다. 이동한 bind source만 새 경로로 대응했다.
- 2026-09-14: 환경설정 31개·서버 checkout 6개·라우팅/Nginx 3개·agent 12개 테스트(총 52개)가 통과했다. Compose 검사, 전체/범위별 env 검사, k8s-render/export, 앱별 server-check, 문서 감사·링크, Shell 문법, skill 메타데이터 및 git diff --check가 통과했다.
- 2026-09-14: L3 Spider mock 데이터 도구의 Python 구문과 저장소 루트 계산을 검증했다. 실제 mock 데이터 생성은 하지 않았으며 출력 위치는 기존 data/l3_spider/daily_anomaly를 유지했다.
- 2026-09-14: 기존 파일·스테이징 항목을 보존했다. 현재 개발 checkout에는 sparse 설정을 적용하지 않았고 사내 서버 변경·실제 배포·commit/push는 수행하지 않았다.
