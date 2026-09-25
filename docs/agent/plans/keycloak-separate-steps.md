# ExecPlan: Keycloak 단계별 실행 파일

## 목표
- Realm → IdP → User Profile → IdP mapper → Portal client/token mapper → 선택 SDWT 순서를 독립 실행한다.

## 현재 상태
- 통합 discovery 명령은 IdP·프로필·mapper를 연속 실행한다.
- claim 스크립트는 프로필과 mapper를 함께 변경한다.

## 범위
- Keycloak 실행 파일, Job 지원 스크립트, 렌더 정의, Makefile, 문서 및 관련 테스트.
- etch realm·oidc alias와 기존 통합 명령 계약은 유지한다.

## 설계
- 번호가 있는 shell 진입점 6개가 기존 도구를 재사용한다.
- realm은 목록 조회 성공 후 없을 때만 기본 JSON으로 생성한다.
- 프로필 전용/mapper 전용 모드를 추가하고 단계별 Job 이름을 분리한다.
- 필요한 단계만 discovery 또는 Portal env를 읽는다. SDWT는 기존 별도 관리자 인증·CSV 계약을 사용한다.

## 실행 단계
- [x] 독립 단계와 realm 생성 구현
- [x] Make 진입점·문서·렌더 갱신
- [x] 단계별 변경 범위 및 재실행 회귀 검사

## 검증
- discovery, environment, server-checkout, SDWT 관련 테스트
- server-check, k8s-export, shell 문법 및 문서 링크 검사

## 위험과 대응
- 기존 realm 보존: 생성 전 목록 조회, 이미 있으면 무변경 종료.
- 프로필·mapper 결합: 전용 모드의 쓰기 경로를 테스트한다.
- 실제 클러스터에는 적용하지 않으며 로그인 검증은 운영에서 수행한다.

## 진행 기록
- 2026-09-25: 사용자가 realm부터 각 단계를 독립 실행하는 파일을 요청했다.
- 2026-09-25: 00~05 실행 파일과 Make 명령을 추가했다. 기존 realm 무변경, 조회 오류 시 생성 금지, 프로필/mapper 쓰기 분리, 단계별 단일 Job 실행을 검증했다.
- 2026-09-25: discovery 16개, environment/server-checkout 58개, Keycloak up 13개, SDWT 6개 통과(총 93개). 시험 서버가 필요한 SDWT 통합 9개는 건너뛰었다.
- 2026-09-25: server-check, k8s-export, 6개 실행 파일 help·실행 권한, shell·문서 예제 문법, 문서 링크, 실제 Job 원본 변환, CSV 검증 통과. 클러스터 적용은 수행하지 않았다.
