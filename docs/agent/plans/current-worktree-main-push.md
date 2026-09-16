# ExecPlan: 현재 워크트리 main 반영

## 목표
- 사용자가 요청한 현재 워크트리 전체 변경을 커밋하고 origin/main에 반영한다.

## 현재 상태
- feat/k8s-keycloak-local, main, origin/main의 시작 커밋은 eb880ab7로 동일하다.
- 앱 경로 재편, Kubernetes 배포, 인증, 개발 설정, 문서와 agent 도구 변경이 포함되어 있다.

## 범위
- 현재 추적·미추적 변경 전체. ignored 실제 설정·데이터는 제외한다.
- 실제 서버 배포는 수행하지 않는다.

## 설계
- 현재 브랜치에서 검증 후 커밋하고 main으로 fast-forward 병합한다.
- 원격 변경이 발생하면 강제 push하지 않는다.

## 실행 단계
- [x] 원격 main과 작업 트리 확인
- [x] 검증과 stage 결과 점검
- [x] 커밋·main 병합·push 실행 준비 (결과는 Git 이력과 원격으로 확인)

## 검증
- make audit, tooling-test, compose-check
- make web-lint web-test web-build
- Compose api 임시 컨테이너에서 ENVIRONMENT=test로 check, migration drift, 전체 테스트
- stage diff 공백 검사와 main 원격 커밋 일치 확인

## 위험과 대응
- 다수 파일 이동: rename 탐지 결과와 미추적 파일 포함 여부를 확인한다.
- 기본 dev 관리자와 테스트 충돌: 저장된 env를 바꾸지 않고 테스트 프로세스만 ENVIRONMENT=test로 실행한다.

## 진행 기록
- 2026-09-15: 사용자의 현재 워크트리 전체 main push 요청에 따라 시작했다.
- 2026-09-15: audit·tooling 60개·Compose 검사, Web lint·206개 테스트·빌드, Django check·migration 변경 없음·1,142개 테스트, Airflow DAG 5개, 전체 앱 Kubernetes/Helm 원본 검사 통과. 개발 entrypoint의 테스트 환경 거부는 임시 API 컨테이너에서 entrypoint를 sh로 지정해 해결했다. 문서 EOF 빈 줄 한 곳을 정리했다.
