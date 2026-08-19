# ExecPlan: 워크트리 리뷰 회귀 수정

## 목표
- Assistant 이메일 근거 링크가 canonical 메일함 query를 사용하게 한다.
- canonical 오류 변환 후에도 원본 HTTP 응답 메타데이터를 보존한다.
- Observer API 문서를 현재 등록된 endpoint와 일치시킨다.

## 현재 상태
- 이메일 근거 링크는 제거된 `user_sdwt_prod`를 생성하지만 메일 화면은 `userSdwtProd`만 읽는다.
- 오류 미들웨어는 legacy JSON을 새 `JsonResponse`로 교체해 원본 header와 cookie를 잃는다.
- Observer 문서는 테스트와 URLConf에서 제거한 legacy endpoint를 계속 안내한다.

## 범위
- 수정: Assistant 이메일 링크 유틸과 테스트, 공통 오류 미들웨어와 테스트, Observer API 문서.
- 제외: DB, 권한, 환경변수, 현재 canonical API body와 Observer route 변경.

## 설계
- 이메일 링크는 `userSdwtProd`와 `emailId`만 생성한다.
- 오류 변환 응답에 원본의 content 전용 header를 제외한 header와 cookie를 복사한다.
- Observer 문서에는 현재 URLConf의 metadata/page/detail/evidence/TKIN endpoint만 남긴다.

## 실행 단계
- [x] 이메일 근거 링크 query를 수정하고 직접 URL 회귀 테스트를 추가한다.
- [x] 오류 응답 header/cookie 보존 로직과 회귀 테스트를 추가한다.
- [x] Observer endpoint 표·query 규칙·예시를 현재 route로 갱신한다.
- [x] 관련 테스트와 경계 감사를 실행한다.

## 검증
- `npm run web:test -- --run src/features/assistant/utils/buildEmailSourceUrl.test.js src/features/assistant/components/ChatMessages.test.jsx`
- `npm run web:test && npm run web:lint && npm run web:build`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test api.common.tests.CommonMiddlewareErrorContractTests`
- `docker compose -f docker-compose.test.yml run --rm api-test python manage.py test api.common api.account api.activity api.appstore api.data_movement api.emails api.voc`
- `npm run agent:audit`

## 위험과 대응
- 위험: 원본 `Content-Length`를 복사하면 새 body 길이와 달라질 수 있다.
- 대응: content 전용 header는 복사하지 않고 Django가 새 응답 기준으로 계산하게 한다.
- 위험: 문서에서 아직 유효한 endpoint를 함께 지울 수 있다.
- 대응: `api.observer.urls`와 endpoint 표를 직접 대조한다.

## 진행 기록
- 2026-08-19: 워크트리 리뷰에서 확인된 세 회귀의 수정 범위와 검증 방법을 확정했다.
- 2026-08-19: 이메일 URL, 오류 transport metadata, Observer 문서를 수정하고 회귀 테스트를 추가했다.
- 2026-08-19: Web 201개 테스트·lint·build, 영향 API 557개 테스트, 전체 agent audit를 모두 통과했다.
