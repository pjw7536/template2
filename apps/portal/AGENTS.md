# Portal 개발 지침

## 작업 시작과 탐색
- 이 지침은 apps/portal 전체에 적용한다. 에디터·에이전트는 이 폴더에서 시작하며 단일 영역 작업은 web 또는 api에서 시작할 수 있다.
- Web 수정은 web/AGENTS.md, API 수정은 api/AGENTS.md를 읽는다. 양쪽을 수정할 때만 둘 다 읽는다.
- 기본 검색은 대상 web/src/features/<feature> 또는 api/api/<feature>로 제한한다. 공통 코드·공개 facade·라우팅은 실제 의존이 있을 때 확인한다.
- 관련 계약·문서가 필요하면 [시작 문서](README.md)의 작업별 진입점을 사용한다. 전체 소스·docs·deploy를 먼저 나열하거나 읽지 않는다.
- Airflow와 설치형 제품의 운영 설정은 기본 탐색 대상이 아니다. 연동 변경 시 관련 앱의 공개 계약까지만 확장하고 내부 코드를 직접 import하지 않는다.

## 외부 영역을 읽는 조건
- auth/RAG/assistant/mail 계약·env·mock 변경: ../../local/AGENTS.md와 루트 `.codex/skills/offsite-dev-contract-sync/SKILL.md`를 적용한다. 사내망 없이 개발 흐름이 유지되어야 한다.
- 배포 이미지·운영 env·API 파일 마운트 계약 변경: ../../deploy/AGENTS.md와 관련 Portal 설정을 확인한다. 로컬에도 영향이 있으면 local 지침을 함께 적용한다.
- API 파일 데이터 경로는 /data/<domain>, Django 설정은 <DOMAIN>_DATA_ROOT를 사용한다. 상세 read-only·마운트 동기화 규칙은 deploy/AGENTS.md의 파일 데이터 계약을 따른다.
- 실행 실패는 관련 명령·설정부터 확인하고, 검사 도구 수정이 필요할 때만 apps/tooling 구현을 읽는다.

## 실행과 검증
- 명령 표는 README.md를 기준으로 한다. 이 폴더에서는 `make -C ../.. <target>`, web/api에서는 `make -C ../../.. <target>`으로 루트 Makefile을 호출한다.
- make dev는 전체 로컬 Kubernetes 앱을 기동한다. 에이전트 작업 범위가 Portal이어도 실행 환경 전체를 읽을 필요는 없다.
- Django 테스트·명령은 Docker Compose api 컨테이너에서 실행한다. 소스가 이미지에 포함되므로 변경 후 이미지 갱신 또는 명시적 소스 마운트가 필요하다. 세부 절차는 django-test-migration-flow 스킬을 따른다.
- UI는 관련 Web 검사, 업무 로직은 관련 API 테스트, 경계 변경은 해당 boundary audit을 실행한다. 작은 작업에 전체 make audit을 기본 적용하지 않는다.
