# ExecPlan: 앱별 소스·배포 구조 정리

## 목표
- 소스는 apps/<app>, 배포는 deploy/<app>, 개발 설정은 local/<app>에 배치한다.
- 서버 기본 checkout에는 소스를 제외하고 --with-source로 선택한다.

## 현재 상태
- Portal 소스는 apps/api와 apps/web, Airflow 소스는 airflow에 있다.
- 기존 변경사항 247개를 보존하며 자동 stage·commit·push하지 않는다.
- 사전 검사: Agent 단위 테스트 12개, 저장소 회귀 테스트 48개 통과. Helm 미설치.

## 범위
- Airflow·Portal 경로, 이미지 빌드, Compose, checkout, Agent 규칙·검사·문서.
- API·DB·인증·업무 로직과 운영 PV는 유지한다. 실제 서버 배포 및 DB 초기화는 제외한다.

## 설계
- Portal은 apps/portal/{api,web}, Airflow는 apps/airflow/{dags,tests,plugins,image}.
- Airflow 이미지 빌드는 앱 source context만 사용하고 deploy 명령은 소스 없이 동작한다.
- 공통 설정은 deploy/airflow/config, 개발 설정은 local/airflow/config, 새 로그는 data/airflow/logs.
- 기존 로그는 이관·삭제하지 않는다. 기존 단독 Compose 진입점과 AIRFLOW_PROJ_DIR 명시값은 호환 유지한다.
- deploy/shared/apps.json을 checkout·구조 검사의 공통 앱 목록으로 사용한다.
- 이전 사내 Compose와 root 명령은 보존한다. 과거 ExecPlan은 역사 기록으로 유지한다.

## 실행 단계
- [x] Airflow 소스·이미지·설정·로그 mount 이동
- [x] 앱 목록·선택 checkout 및 구조 검사
- [x] Portal 소스·workspace·도구·규칙 이동
- [x] 안내 문서·회귀 테스트 갱신
- [x] 전체 검증 및 결과 기록

## 검증
- npm run agent:audit 및 web:test, web:lint, web:build.
- node --test scripts/tests/*.test.cjs 및 Airflow DAG 단위 테스트.
- Compose 통합·단독·CI·참고용 config 검사와 빌드 context 확인.
- Compose api 컨테이너에서 make test-api, check-api, makemigrations-check.
- 임시 sparse checkout 기본/소스 포함 경로와 소스 없는 서버 검사.
- Helm·사내 이미지 빌드는 도구·네트워크 제약이 있으면 미검증 사유를 기록한다.

## 위험과 대응
- 기존 미커밋 변경은 현재 파일을 이동해 보존하며 reset·stash하지 않는다.
- lockfile은 경로만 갱신하고 의존성 버전을 바꾸지 않는다.
- 실제 env는 내용 출력 없이 이동하며 생성 데이터·가상환경은 재생성 대상으로 둔다.
- 경로 변경에 따른 감사 기준선은 경로만 이동하고 허용 기준을 완화하지 않는다.

## 진행 기록
- 2026-09-15: 사용자 확정 계획을 기록하고 구현 시작.
- 2026-09-15: Portal 소스 파일과 Airflow DAG·테스트를 이동했다. 업무 코드는 deflate_csv 오류 안내의 경로 외에 변경하지 않았다.
- 2026-09-15: Docker Compose config·실제 API 이미지 빌드·Airflow 최종 이미지 빌드 및 포함 파일 확인 통과. 기존 로그는 복사하지 않았다.
- 2026-09-15: Helm 3.19.0 공식 archive의 checksum을 검증해 ignored .tools/bin에 설치했다. 고정 chart로 전체 앱 server-check 및 소스 없는 checkout 검사가 통과했다.
- 2026-09-15: 깨끗한 npm ci에서 기존 peer 의존성 @testing-library/dom 누락을 발견했다. 기존 lockfile 버전 10.4.1을 직접 devDependency로 명시하고 두 lockfile을 동기화했다. 의존성 버전 업그레이드는 없다.
- 2026-09-15: 기본 개발 env의 API 전체 테스트 1,142개 중 Keycloak 권한 테스트 1개 실패. development의 dummy 슈퍼유저 초기화와 테스트 기대값의 충돌이다. 관련 auth·account·settings 파일은 이동 전 index와 byte 단위로 동일함을 확인했다. ENVIRONMENT=test에서 해당 테스트 통과 후 전체 재검증 중이다.
- 2026-09-15: `docker compose -f docker-compose.dev.yml exec -T -e ENVIRONMENT=test api python manage.py test`로 전체 1,142개 통과. 기본 dev env·인증 로직은 변경하지 않았고 테스트 실행 방법을 Portal README에 기록했다.
- 2026-09-15: 최종 검증은 아래와 같다.
  - `npm ci --legacy-peer-deps` 후 `npm run web:test`: 54개 파일·206개 테스트 통과.
  - `npm run web:lint`, `npm run web:build`: 통과. 기존 큰 chunk 안내는 유지.
  - `npm run agent:audit`: 단위 테스트 16개와 전체 경계·구조·문서 검사 통과.
  - `PATH="$PWD/.tools/bin:$PATH" node --test scripts/tests/*.test.cjs`: 56개 통과. checkout 인자 검증 보강 후 해당 13개, 이미지 source 검사 보강 후 Airflow 배포 테스트 재통과.
  - `python3 -m unittest discover -s apps/airflow/tests -v`: 5개 통과.
  - `PATH="$PWD/.tools/bin:$PATH" make server-check APP=all`: Keycloak·Portal·Airflow·FTP·Monitoring 실제 원본 렌더 검사 통과.
  - `bash scripts/agent/check_compose_configs.sh`와 통합·단독 기본/사용자 지정 mount 회귀 검사 통과.
  - `make check-api makemigrations-check`: 통과, migration 변경 없음.
  - `docker compose -f docker-compose.test.yml build api-test`: 통과.
  - 공개 기본 Airflow 이미지를 사용한 최종 Docker 이미지 빌드와 DAG·플러그인·초기화 코드 포함 검사 통과. 사내 mirror·ODBC 의존성 이미지 빌드는 외부 PC에서 실행하지 않았으며 기존 인자 계약은 테스트로 확인.
  - 이동 전 index와 새 앱 파일을 비교해 누락 없음·DAG 내용 동일·업무 코드 유지 확인. 현재 문서 상대 링크와 `git diff --check` 통과.
- 2026-09-15: 검증을 위해 시작한 API 컨테이너를 중지해 기존 실행 상태(PostgreSQL만 실행)를 복원했다. 실제 서버 배포·commit·push는 실행하지 않았다.
