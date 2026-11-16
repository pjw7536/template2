# Portal 개발 지침

## 시작과 탐색

- `apps/portal/**`에 적용한다. 이 폴더 또는 단일 작업 영역인 web/api에서 시작한다.
- Web 작업은 [web/AGENTS.md](web/AGENTS.md), API 작업은 [api/AGENTS.md](api/AGENTS.md)를 읽는다. 양쪽을 바꿀 때만 둘 다 읽는다.
- 탐색은 `web/src/features/<feature>` 또는 `api/api/<feature>`부터 시작한다. 작업별 계약·문서는 [README](README.md)에서 선택한다.
- Airflow·설치형 제품의 내부 소스·운영 문서는 기본 탐색 대상이 아니다. 연동 시 필요한 공개 계약부터 확인한다.

## 외부 영역을 확인할 조건

| 변경 | 함께 확인 |
| --- | --- |
| auth/RAG/assistant/mail 계약·env·mock | [local 지침](../../local/AGENTS.md), 루트 `offsite-dev-contract-sync` 스킬 |
| 배포 이미지·운영 env·API 파일 마운트 | [deploy 지침](../../deploy/AGENTS.md)의 데이터 계약과 관련 Portal 정의. 로컬에도 영향이 있으면 local 지침 |
| 실행 실패 | 관련 명령·설정부터 확인하고 검사 도구 수정이 필요할 때만 `apps/tooling` 구현 |

## 실행

- 명령 표는 README를 따른다. 루트 Makefile은 이 폴더에서 `make -C ../.. <target>`, web/api에서 `make -C ../../.. <target>`으로 호출한다.
- `make dev`는 전체 로컬 Kubernetes 앱을 기동한다. 준비된 환경을 재사용하고, Portal 코드 작업을 이유로 전체 실행 설정을 선독하지 않는다.
- 검증은 Web/API 하위 지침에서 변경에 맞게 선택한다. 작은 작업에 전체 `make audit`을 기본 적용하지 않는다.
