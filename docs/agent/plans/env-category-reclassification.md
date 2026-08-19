# ExecPlan: 환경변수 카테고리 재분류

## 목표
- API와 Airflow 환경변수를 도메인 소유권과 실행 profile에 맞게 재배치한다.
- 환경변수 key 계약과 각 dev/OIDC/prod 환경의 최종 유효 값은 유지한다.

## 현재 상태
- 공용 RAG 설정이 Assistant 전용 섹션으로 표시되어 있다.
- 실제 RAG/RACB endpoint가 API 공통 env에 있어 profile 경계가 불명확하다.
- Emails POP3/OCR과 Drone CTTTM/전송 채널 설정이 같은 settings 섹션에 섞여 있다.
- dev OCR token과 L3 Spider 발신자 override가 Knox Mail 섹션에 함께 있다.
- OIDC와 prod profile에 동일한 서버 endpoint/origin 설정이 반복되어 있다.

## 범위
- 수정: `apps/api/config/settings.py`, `env/api*.env`, `compose/oidc.app.yml`, `compose/prod.app.yml`, 환경 설정 문서.
- 검증: `compose/dev.app.yml`, `apps/adfs_dummy`, dev/OIDC/prod/test Compose 렌더.
- 제외: 환경변수 key rename, endpoint 경로 변경, API/DB/auth 계약 변경.

## 설계
- `env/api.common.env`에는 모든 profile이 공유할 안전한 기본값만 둔다.
- `env/api.server.common.env`에는 OIDC/prod가 공유하는 서버 origin, OIDC, RAG/RACB endpoint와 RAG 인증 header를 둔다.
- OIDC/prod profile에는 실행 모드, 보안 토글, 인증서처럼 서로 다른 값만 둔다.
- dev profile은 `apps/adfs_dummy` endpoint와 개발용 token만 override한다.
- Django settings는 공용 RAG, Emails POP3, Emails OCR, Drone CTTTM, Drone 전송 채널을 별도 섹션으로 나눈다.
- DB, migration, public API, auth callback 변화는 없다.

## 실행 단계
- [x] 공통 env의 RAG/RACB 값을 안전한 기본값으로 바꾸고 섹션을 분리한다.
- [x] dev/OIDC/prod profile에 환경별 endpoint와 인증 설정을 배치한다.
- [x] Django settings의 도메인별 섹션을 재배치한다.
- [x] 환경 설정 문서에 profile 소유권과 RAG 분류를 반영한다.
- [x] Compose와 Django 설정 검사를 실행한다.
- [x] OIDC/prod 공통 서버 설정을 `api.server.common.env`로 추출한다.
- [x] Compose env_file 순서를 공통 → 서버 공통 → profile 순으로 변경한다.
- [x] 서버 profile과 공통 env 사이의 불필요한 동일값 중복을 제거한다.
- [x] 문서 inventory와 운영 env 목록을 새 계층에 맞춘다.
- [x] profile별 최종 주입값과 중복 0건을 다시 검증한다.

## 검증
- `bash scripts/agent/check_compose_configs.sh`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py check`
- `docker compose -f docker-compose.yml run --rm --no-deps -e ADFS_CER_PATH=/app/dummy_adfs_public.cer --entrypoint python api manage.py check`
- `git diff --check`
- legacy RAG key와 env 중복 할당 검색

## 위험과 대응
- 위험: profile 이동 과정에서 endpoint나 header의 최종 값이 누락될 수 있다.
- 대응: Compose 렌더 결과와 profile별 key 목록을 변경 전 계약과 대조한다.
- 위험: offsite dev가 사내 endpoint로 fallback할 수 있다.
- 대응: dev profile에서 네 RAG endpoint와 dummy Mail endpoint를 명시적으로 유지한다.
- 위험: 새 env_file을 배포 서버에 누락하면 OIDC/RAG 설정이 비어 기동 후 외부 연동이 실패한다.
- 대응: OIDC/prod Compose가 새 파일을 필수로 읽게 하고 Compose 렌더 검사를 배포 전 검증에 유지한다.

## 진행 기록
- 2026-08-19: key rename 없이 도메인 섹션과 profile 소유권만 재분류하기로 결정했다.
- 2026-08-19: 공통 RAG/RACB 값을 안전한 기본값으로 바꾸고 실제 endpoint/header를 OIDC/prod profile로 이동했다.
- 2026-08-19: dev/OIDC/prod/test 최종 주입값, Compose 렌더, test/prod Django system check와 diff 형식을 검증했다.
- 2026-08-19: OIDC/prod만 사용하는 서버 구성의 반복값을 제거하기 위해 `api.server.common.env` 계층을 추가하기로 결정했다.
- 2026-08-19: 서버 공통 env를 Compose에 연결하고 OIDC/prod profile에는 서로 다른 10개 실행·보안·인증서 값만 남겼다.
- 2026-08-19: 서버가 읽는 모든 env 계층 간 key 중복 0건, OIDC/prod 최종 주입값 유지, Compose와 Django system check 통과를 확인했다.
