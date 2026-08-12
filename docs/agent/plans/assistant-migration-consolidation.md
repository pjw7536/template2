# ExecPlan: Assistant 초기 마이그레이션 통합

## 목표
- 서버에 아직 적용되지 않은 `assistant` 마이그레이션 체인을 최종 모델 상태의 단일 `0001_initial.py`로 통합한다.
- 보존할 필요가 없는 로컬 Assistant 데이터와 기존 마이그레이션 적용 이력을 제거하고 새 초기 마이그레이션을 검증한다.

## 현재 상태
- `apps/api/api/assistant/migrations/0001_initial.py`부터 `0004_assistantconversationsummary.py`까지 신규·미추적 파일로 존재한다.
- 서버에는 해당 마이그레이션이 적용된 적이 없다.
- 로컬 개발 DB에는 네 마이그레이션이 모두 적용되어 있다.
- 다른 앱의 마이그레이션은 `assistant` 마이그레이션을 의존하지 않는다.
- 기존 데이터 변환용 `RunPython` 연산이 `0003`, `0004`에 있다.

## 범위
- `assistant` 앱의 로컬 테이블과 데이터만 롤백한다.
- 기존 `0001~0004`를 최종 모델 기준 단일 `0001_initial.py`로 교체한다.
- 다른 앱의 모델, 마이그레이션, 데이터와 Assistant 업무 로직은 변경하지 않는다.

## 설계
- 기존 마이그레이션 파일이 존재하는 상태에서 `assistant zero`로 로컬 스키마와 적용 이력을 정상 역순 롤백한다.
- 기존 번호 마이그레이션을 제거한 뒤 `makemigrations assistant`로 현재 모델 상태를 직접 표현하는 초기 마이그레이션을 생성한다.
- 신규 DB 경로에는 이전 데이터가 없으므로 기존 데이터 이관용 `RunPython`은 포함하지 않는다.
- API, 인증, 환경 변수 계약에는 영향이 없다.

## 실행 단계
- [x] 로컬 `assistant` 마이그레이션을 zero로 롤백한다.
- [x] 기존 `0001~0004` 파일을 제거한다.
- [x] 현재 모델 기준 단일 `0001_initial.py`를 생성한다.
- [x] 새 초기 마이그레이션을 로컬 DB에 적용한다.
- [x] 마이그레이션 상태와 Assistant 회귀 테스트를 검증한다.

## 검증
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py showmigrations assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py makemigrations assistant --check --dry-run`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py migrate assistant`
- `docker compose -f docker-compose.dev.yml exec -T api python manage.py test api.assistant`

## 위험과 대응
- 위험: 롤백 과정에서 로컬 Assistant 대화와 메시지가 삭제된다.
- 대응: 사용자가 데이터 폐기와 무백업을 명시적으로 승인했다.
- 위험: 다른 앱이 Assistant 마이그레이션을 의존하면 zero 롤백이 막힐 수 있다.
- 대응: 사전 검색에서 외부 마이그레이션 의존성이 없음을 확인했다.

## 진행 기록
- 2026-08-12: 서버 미적용, 로컬 데이터 폐기 승인, 단일 초기 마이그레이션 재생성 방식을 확정했다.
- 2026-08-12: 기존 네 마이그레이션을 zero로 롤백하고 최종 모델 기준 새 `0001_initial.py`를 생성·적용했다.
- 2026-08-12: migration drift 검사와 Assistant 테스트 46개가 통과했다.
