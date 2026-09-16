# ExecPlan: Portal 운영 환경을 Kubernetes prod로 통합

## 목표

- Portal 운영 입력과 overlay 이름을 prod로 통일하고 internal 중복을 없앤다.
- Keycloak 연결과 기존 업무 연동값을 보존하며 로컬 Compose 개발을 유지한다.

## 현재 상태

- prod API는 ADFS 기반 Compose 입력 146개, internal API는 미완성 K8s 입력 25개다.
- prod 실제 env는 Git 제외되지 않으며 검사기가 oidc와 동일한 key 구성을 강제한다.
- Compose API는 MinIO env를 함께 읽지만 K8s API는 자체 env만 읽는다.

## 범위

- env, 운영 overlay 경로, Makefile·검사 도구·테스트·관련 문서를 수정한다.
- 실제 배포, Namespace 변경, 업무 API 코드, local/oidc/test 입력값은 변경하지 않는다.
- 기존 Compose 정의는 참고용으로 유지하지만 prod 시작 명령은 운영 전환 안내로 차단한다.

## 설계

- 실제 prod 파일은 Git 제외·600 권한으로 유지한다. 기존 Compose 입력은 같은 폴더의 Git 제외 *.pre-k8s.bak 사본에 보존한다.
- API는 internal 기동·인증값을 기준으로 하고 기존 prod의 나머지 업무·조정값을 보존한다. 미입력 DNS·DB는 준비 중 상태를 유지하며 검사에서 차단한다.
- Web은 기존 화면 링크를 보존하고 새 운영 공개 주소는 template을 기준으로 준비한다. MinIO 계정은 보존하고 파일 API·콘솔 공개 주소를 분리한다.
- API에 필요한 MinIO 접근 계정만 명시적으로 보존하며 관리자 계정은 API에 넣지 않는다.
- 공개 예시는 비밀값 없는 기존 internal 예시에서 이동한다. prod 검사 계약을 oidc Compose와 분리하고 선택 업무 연동을 기동 필수로 강제하지 않는다.
- prod overlay는 이름만 변경한다. Namespace와 렌더링된 리소스는 동일하게 유지한다.

## 실행 단계

- [x] 기준 해시와 복구용 입력을 확보한다.
- [x] 실제 입력·예시를 prod로 통합하고 Git 제외 규칙을 갱신한다.
- [x] 운영 경로, 검사, 안내와 회귀 테스트를 수정한다.
- [x] 보존 검증, 테스트, 렌더링과 문서 검사를 수행한다.

## 검증

- local/oidc/test 파일과 Compose 결과 동일성, 운영 overlay 결과 동일성.
- 기존 업무 설정과 Keycloak 입력 보존, prod 실제 파일·사본 Git 제외 및 권한.
- 환경 검사 테스트, profile key 검사, Kustomize 렌더링, 문서 감사, diff 검사.
- 실제 prod 미입력 상태는 필수값 검사 실패가 정상이다.

## 위험과 대응

- 운영 DNS·DB를 추측하지 않는다. 미입력 검사를 유지하고 배포하지 않는다.
- 이전 Compose 전용 주소가 남을 수 있으므로 업무 연동은 실제 연결 전 확인하도록 안내한다.
- Kubernetes env 전달 방식 차이로 MinIO 계정이 누락되지 않도록 명시적으로 옮기고 검사한다.

## 진행 기록

- 2026-09-11: 사용자가 향후 운영을 Kubernetes로 확정했다. local/oidc/test는 변경하지 않고 운영 입력을 통합한다.
- 2026-09-11: 기존 Compose 입력 3개는 prod의 *.pre-k8s.bak에 보존했다. internal 입력의 25개 할당과 나머지 기존 업무 설정을 값 노출 없이 비교했다. 실제 입력·사본은 모두 Git 제외와 600 권한을 확인했다.
- 2026-09-11: local/oidc/test 파일 및 Compose 결과, prod로 이동한 운영·migration overlay 렌더링 해시가 기준과 동일하다. Namespace를 변경하지 않았다.
- 2026-09-11: 환경 회귀 테스트 22개, agent 테스트 12개, 개발·OIDC·테스트 Compose 검사, 전체 Kustomize 렌더링, 문서 감사, shell 문법과 diff 검사를 통과했다. 실제 prod env가 없는 신규 clone에 해당하는 공개 예시 검사도 통과했다.
- 2026-09-11: 실제 운영 입력은 DNS·DB·Django secret 미입력으로 검사가 실패한다. 이 상태를 숨기거나 실제 값을 추측하지 않았으며 클러스터 적용·DB 변경·로그인 테스트는 수행하지 않았다.
