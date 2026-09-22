# ExecPlan: 사내 Kubernetes 전용 정책

## 목표
- 사내 서버의 지원 배포·검사 경로를 Kubernetes로 제한한다.
- 로컬 Compose와 CI 테스트를 유지한다.

## 현재 상태
- Keycloak·Portal에는 prod Kubernetes 정의가 있다.
- Airflow·Monitoring 및 과거 oidc 환경에는 서버 Compose 검사·실행 경로가 남아 있다.

## 범위
- Makefile, 서버 검사, 회귀 테스트, 현재 운영 문서·규칙.
- 기존 설정값과 Compose 참고 파일을 보존한다. 새 Airflow·Monitoring K8s 설계·배포, 실제 서버 작업은 포함하지 않는다.

## 설계
- 사내 Compose 시작·빌드 진입점은 안내 후 중단한다. 기존 컨테이너 정리 명령은 명시적인 legacy 종료 용도로만 보존한다.
- server-check는 Kubernetes 원본만 검사한다. 미전환 앱·환경은 명시적으로 실패한다.
- 전체 종료 명령 down은 로컬 Compose만 대상으로 한다.
- 운영 문서는 실제 K8s 원본 존재와 서비스 배포 준비 완료를 구별한다.

## 실행 단계
- [x] 사내 실행·검사 정책을 수정한다.
- [x] 회귀 테스트와 현재 문서를 동기화한다.
- [x] 로컬·서버 검사와 회귀 검증 결과를 기록한다.

## 검증
- env·서버 checkout·라우팅 테스트, 로컬/CI Compose config, Kustomize 렌더링.
- 미전환 앱·환경 실패 및 사내 Compose 시작 명령 차단 테스트.
- 문서 감사·링크, Shell 문법, git diff --check.

## 위험과 대응
- K8s 정의가 없는 앱이 검사 성공으로 표시되는 문제: 명시적인 미전환 오류로 차단한다.
- 기존 컨테이너를 중지하는 부작용: 실행 명령을 호출하지 않고 Makefile만 수정한다.

## 진행 기록
- 2026-09-14: 사용자가 사내 서버는 Kubernetes만 사용할 계획이라고 명시했다.

- 2026-09-14: OIDC Compose 시작·빌드 명령을 차단했고 down은 로컬만 종료하도록 변경했다. 기존 명시적 legacy 종료 명령과 참고 정의는 보존했다.
- 2026-09-14: server-check에서 Compose 경로를 제거했다. Keycloak·Portal prod는 통과하며 Airflow·Monitoring·과거 oidc는 K8s 정의 부재를 명시하고 실패한다.
- 2026-09-14: 현재 배포·clone·사용방법·환경설정 문서와 AGENTS를 Kubernetes 전용 정책으로 갱신했다. 실제 데이터·서버는 변경하지 않았다.
- 2026-09-14: 환경설정 33개·서버 checkout 6개·라우팅 3개·agent 12개(총 54개) 테스트가 통과했다. Compose config, Kustomize 6개 렌더링, Keycloak·Portal server-check, 문서 감사·링크, Shell 문법과 git diff --check도 통과했다.
