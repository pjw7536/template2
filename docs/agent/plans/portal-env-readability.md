# ExecPlan: Portal 환경파일 가독성 정리

## 목표

- Portal 설정을 처음 배포할 때 읽는 순서로 정리한다.
- API/Web/MinIO 역할과 local/oidc/prod/internal/test 용도를 명확히 한다.
- 기존 설정값을 보존하고 internal Web·MinIO 예시를 완성한다.

## 현재 상태

- API profile에는 기능별 주석은 있으나 필수 입력과 선택적인 조정값이 섞여 있다.
- internal에는 API 예시만 있고 Web·MinIO 입력 안내가 없다.
- 기존 env 경로와 실행 계약은 이미 앱별 구조로 이동했다.

## 범위

- `env/portal`의 파일 정렬·주석·예시와 관련 안내를 수정한다.
- 런타임 key/value, 인증 방식, DB 연결, 배포 구조는 변경하지 않는다.

## 설계

- API는 서버·공개 주소, DB, 로그인, 공용 연동, 업무 기능, 선택 조정 순서로 정리한다.
- Web은 공개 주소·연결·링크·실행 옵션, MinIO는 서버 계정·API 계정·공개 주소 순서로 정리한다.
- 기본값과 같아 보여도 운영자가 지정한 값을 삭제하지 않는다. 선택값 구역에 모아 필요할 때만 수정하도록 안내한다.
- 기존 credential이 포함된 파일은 값을 출력하지 않는 기계적 재정렬로 처리한다.

## 실행 단계

- [x] 기존 key/value와 Compose 결과를 기준으로 확보한다.
- [x] profile 파일을 동일한 기준으로 정리한다.
- [x] Portal 전용 README와 internal Web·MinIO 예시를 추가한다.
- [x] 설정 동등성, profile 검사, Compose와 문서를 검증한다.

## 검증

- 각 기존 파일의 key/value 및 권한이 동일한지 비교한다.
- Compose dev/oidc/prod/test의 병합 결과와 로컬 API 합성 결과를 비교한다.
- `make env-profile-key-check`, `make k8s-render`, 문서 감사, `git diff --check`.

## 위험과 대응

- 위험: env 재정렬이 참조 순서나 값을 바꿀 수 있다.
- 대응: 원본 행을 그대로 이동하고 Compose 병합 결과까지 비교한다.
- 위험: 빈 값 제거로 코드 기본값이 대신 적용될 수 있다.
- 대응: 빈 값도 그대로 유지한다.

## 진행 기록

- 2026-09-11: Portal 환경설정의 가독성과 입력 안내 개선을 시작했다.
- 2026-09-11: 기존 env 13개를 공통 구역 순서로 재정렬했다. 원본 할당 행과 파일 권한을 보존했으며 새 internal Web·MinIO 예시와 Portal 전용 README를 추가했다.
- 2026-09-11: 변경 전후 key/value·권한, Compose dev/oidc/prod/test의 정규화된 결과, 로컬 Kubernetes API 합성 결과의 해시가 모두 일치했다. 실제 값은 출력하지 않았다.
- 2026-09-11: 환경 회귀 테스트 15개, profile key 검사, Kustomize 전체 렌더링, 문서 감사와 diff 검사가 통과했다. 인증 계약 변경이 없어 dummy·API 코드는 수정하지 않았으며 실제 클러스터 배포와 로그인 테스트는 수행하지 않았다.
