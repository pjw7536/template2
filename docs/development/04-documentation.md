# 문서 작성 기준

[문서 홈](../README.md)

## 위치

| 내용 | 원본 |
| --- | --- |
| 개발 PC 실행·일상 명령 | `docs/getting-started/` |
| 구조·모델·외부 연동 | `docs/concepts/` |
| 소스 수정·migration | `docs/development/` |
| 기능·화면·권한·API 계약 | `docs/features/` |
| 설정·구현 색인·관리 명령 | `docs/reference/` |
| 서버 설치·운영 | `deploy/<app>/docs/`, `deploy/shared/docs/` |
| 현재 사내 운영 정보 | `deploy/shared/docs/infrastructure/` |
| 개발 PC 설정·mock | `local/` |
| 에이전트 작업 규칙 | `AGENTS.md`, `docs/agent/` |

## 내용

- 목적·준비 조건·실행 위치·명령·기대 결과·실패 확인을 순서대로 작성합니다.
- 현재 동작·입력·제약·남은 확인만 기록합니다. 완료 이력·변경 경위·미래 재배치 권고는 본문에 누적하지 않습니다.
- API는 method·path·auth·query/body·response·error·side effect를 보존합니다.
- 운영 주소·상태·담당자는 인프라 원본 하나에서 관리하고, 다른 문서는 그 원본을 연결합니다.
- 실제 운영값과 저장소 선언·예시를 구분합니다. 비밀값은 문서에 복사하지 않습니다.
- 조회·검사·적용·삭제의 대상을 밝히고 백업·복구·권한·호환 제약을 삭제하지 않습니다.

## 파일과 검증

앱 배포 문서는 준비·설치·운영 순서의 두 자리 번호를 사용합니다. 짧은 설명만으로 파일을 나누지 않습니다.
README에는 작업과 원본 링크만 두고 상세 절차·긴 파일 목록을 반복하지 않습니다.
이동 시 이전 경로를 남기지 않고 내부 링크·제목 앵커·검사 도구의 참조를 함께 갱신합니다.
`README.md`, `AGENTS.md`, `SKILL.md`, `PLANS.md`는 고정 이름을 유지합니다.

문서 변경 후 `make audit-docs`와 상대 링크·앵커를 검사합니다. 검사 도구를 수정했으면 `make audit-tools-test`,
배포 문서를 이동했으면 `node --test apps/tooling/tests/server-checkout.test.cjs`도 실행합니다.
정적 검사는 실제 서버 적용·접속 검증과 구분합니다.
