# ExecPlan: Portal 중심 에이전트 작업 범위

## 목표
- 같은 저장소에서 Portal 개발의 초기 지침과 파일 탐색을 좁히고 운영 설정은 필요할 때 읽는다.

## 현재 상태
- 소스는 이미 apps/portal에 분리되어 있지만 루트 AGENTS.md에 개발·운영 상세 규칙이 함께 있다.
- make dev는 전체 로컬 kind 환경을 기동하며 Django 검사는 일회성 Compose api를 사용한다.
- 작업 시작 시 Kubernetes 구성 정리의 미커밋 변경이 존재한다. 해당 변경을 보존하고 현재 파일을 기준으로 편집한다.

## 범위
- 루트·Portal·Web·API·deploy·local 지침, Portal 시작 문서, 관련 스킬·평가 안내를 정리한다.
- 소스 코드, Makefile, env, 배포 정의, 체크아웃 방식, 공개 API·DB 계약은 변경하지 않는다.

## 설계
- 루트는 공통 규칙과 작업별 진입점, Portal은 좁은 탐색과 조건부 외부 계약 확인을 소유한다.
- 기존 API·Web 아키텍처 규칙은 유지하고 해당 영역에서 사용할 스킬만 연결한다.
- 운영·마운트 상세는 deploy, 로컬 실행 상세는 local로 이동한다. Git scope 목록은 필요할 때 읽는 문서로 분리한다.
- 명령은 현재 루트 Makefile을 기준으로 안내하며 삭제된 Compose와 host Django 실행 예시를 제거한다.

## 실행 단계
- [x] 지침 분리와 Portal 시작 문서 정리
- [x] 관련 스킬·평가·Git 상세 안내 동기화
- [x] 정적 검사와 대표 작업의 탐색 경로 검토
- [x] 결과·제한·지침 크기 비교 기록

## 검증
- make audit-layout audit-docs
- 수정한 스킬에 skill-creator/scripts/quick_validate.py 실행
- 새 문서 링크, Makefile 명령 dry-run, 삭제된 경로 참조 점검
- UI·API·인증 변경 평가 시나리오의 지침 라우팅 정적 검토
- 초기 지침 바이트 수를 변경 전과 비교한다. 새 에이전트 세션의 실제 토큰·파일 읽기 횟수는 별도 세션 측정 전까지 성공을 주장하지 않는다.

## 위험과 대응
- 상세 규칙이 이동 중 유실되지 않도록 원본과 비교하고 계약 변경 시 읽을 문서 연결을 남긴다.
- 기존 미커밋 변경은 작업 시작 시 임시 디렉터리에 보관한 편집 대상 원문과 비교해 보존 여부를 확인한다.
- 현재 이미지 기반 Django 검사에서 소스 변경·migration이 누락되지 않도록 이미지 갱신과 소스 마운트 조건을 안내한다.

## 진행 기록
- 2026-09-16: 승인된 계획에 따라 문서·지침 범위의 구현 시작. 실행 환경 변경과 커밋은 제외한다.
- 2026-09-16: 루트 지침을 155줄·10,041 bytes에서 38줄·4,405 bytes로 축소했다. Portal 공통 지침을 포함한 기본 합계는 6,914 bytes(31.1% 감소), Web 지침 포함 11,698 bytes(17.9% 감소), API 지침 포함 11,674 bytes(18.6% 감소)다. 사용자 전역 지침·스킬 목록은 비교에서 제외했다.
- 2026-09-16: UI는 Portal→Web→VOC, API는 Portal→API→VOC, 메일 연동은 Portal→API→local 지침·offsite 스킬→env/mock으로 이어지는 경로를 정적으로 검토했다. 새 세션 행동·토큰 실측은 수행하지 않았으며 별도 평가 시나리오를 추가했다.
- 2026-09-16: make audit-docs, 수정한 두 스킬의 quick_validate, 문서 상대 링크 47개, Portal·API 시작 디렉터리의 Makefile dry-run이 통과했다. 기존 스킬 라우팅 12개와 commit scope 22개 보존, 변경 문서의 삭제된 Compose 참조 제거, git diff --check도 확인했다.
- 2026-09-16: make audit-layout은 기존 비관리 디렉터리 apps/web(빈 폴더), airflow(config/dags/plugins/logs) 때문에 실패했다. 사용자 파일 보존을 위해 삭제하지 않았다. 이 실패로 묶음 명령에서 중단된 audit-docs는 별도로 실행해 통과했다.
- 2026-09-16: 기존 Kubernetes 정리에서 갱신한 스킬 명령·env 합성 안내는 보존하고 Portal 시작 경로와 조건부 탐색 안내만 추가했다. Drone 관리 명령 문서에 남아 있던 삭제된 Compose 실행 예시도 현재 api 서비스 명령으로 정정했다.
