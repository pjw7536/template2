# 문서 작성 기준

[문서 홈](../README.md)

## 위치

문서는 읽는 사람과 작업 단위를 기준으로 배치하고, 같은 정보는 한 곳만 원본으로 둡니다. CP1은 저장소 전체를 사용하지만, 서버 검사·배포 도구는 `deploy`와 루트 Makefile만으로 동작해야 하므로([배포 지침](../../deploy/AGENTS.md)) 서버 절차도 `deploy` 안에서 끝나야 합니다.

| 읽는 사람·상황 | 원본 | 담는 내용 |
| --- | --- | --- |
| 서버 운영자(CP1, 서버 checkout) | `deploy/<app>/docs/`, `deploy/shared/docs/` | 설치·배포·운영 절차, 서버 env 작성·검사·Secret 등록, 클러스터·인증서·Ingress |
| 서버 운영자·에이전트 | `deploy/shared/docs/infrastructure/` | 현재 서버·네트워크·서비스·미러·운영 위치와 서버 적용 대기 작업 |
| 개발자(개발 PC 실행) | `docs/getting-started/`, `local/` | 로컬 실행·일상 명령(`docs`), 로컬 주소·계정·mock·데이터 보존(`local`) |
| 개발자(코드 수정) | `docs/concepts/`, `docs/development/`, `docs/features/` | 구조·데이터 모델·외부 연동, 소스 수정·migration 작성, 기능·권한·API 계약 |
| 개발자·운영자 공통 계약 | `docs/reference/` | env 키의 의미·형식, 데이터 마운트 계약, 구현 색인, 관리 명령 |
| 에이전트 | `AGENTS.md`, `docs/agent/` | 작업 규칙·평가·Git 규칙 |

- 서버에서 실행하는 절차는 `deploy`에만 둡니다. `docs`에는 해당 deploy 문서로 가는 링크 한 줄만 둡니다.
- 코드·기능·env 키의 의미는 `docs`에만 둡니다. `deploy`는 서버 값과 절차만 적고 의미는 `docs`로 링크합니다.
- 개발 PC 고유의 값·절차는 `local`에 두고 `docs/getting-started`는 순서와 링크만 제공합니다.
- 같은 정보가 두 곳에 필요하면 한쪽을 원본으로 정하고 다른 쪽은 링크합니다.

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
