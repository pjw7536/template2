# ExecPlan: ChatWidget 방 단위 공유 기억

## 목표
- 같은 ChatWidget 대화방에서 일반 Chat과 Observer를 오가더라도 이전 대화 맥락을 이어서 사용한다.
- Observer 분석의 사실 근거는 현재 Observer 조회 데이터로 제한하고, 이전 대화는 의도와 맥락을 이해하는 배경으로만 사용한다.
- Email RAG 대화 기억은 기존처럼 일반 Chat·Observer와 분리한다.

## 현재 상태
- 프론트엔드는 요청 `contextKey`와 정확히 일치하는 메시지만 모델 이력으로 전송한다.
- 백엔드 rolling summary도 `(conversation, context_key)`별로 조회하고 저장한다.
- 일반 Chat은 `assistant:openwebui`, Observer는 `observer:v1:*`, Email RAG는 `assistant` 문맥을 사용한다.
- 사용자 작업 중인 `useObserverPageState.js`와 해당 테스트 변경은 이 작업에서 수정하지 않는다.

## 범위
- 일반 Chat·Observer 문맥을 같은 방의 공유 기억 그룹으로 해석하는 프론트엔드 이력 선택을 변경한다.
- 공유 기억 그룹의 rolling summary를 조회·생성하도록 Assistant selector/service/view 계약을 변경한다.
- Observer 프롬프트에 현재 조회 데이터 우선과 이전 대화의 비근거성 규칙을 명시한다.
- 문맥 전환 안내 문구와 관련 테스트·문서를 갱신한다.
- 메시지/요약 DB 스키마, 인증, 외부 연동 URL, Email RAG 기억 경계는 변경하지 않는다.

## 설계
- `contextKey`는 요청 라우팅, 현재 데이터 범위, 메시지 출처 식별에 계속 사용한다.
- 별도의 기억 키 해석 함수가 `assistant:openwebui`와 모든 `observer:*`를 `chatwidget:shared`로 묶는다.
- 프론트엔드는 같은 기억 키에 속한 최근 메시지를 시간순으로 전달하며, 메시지 내용에 일반 Chat/Observer 출처를 표시한다.
- 백엔드는 공유 기억 키 요청 시 일반 Chat·Observer 메시지를 함께 요약하고 `chatwidget:shared` summary row에 저장한다.
- Observer 시스템 지침은 현재 `observer_analysis_context_json`만 사실 판단의 근거로 사용하고 대화 이력과 rolling summary는 질문 의도·용어·후속 질문 해석에만 사용하도록 제한한다.
- migration/env/auth 변경은 없다. 기존 문맥별 summary row는 삭제하지 않으며 이후 공유 summary로 자연스럽게 대체한다.

## 실행 단계
- [x] 공유 기억 키와 메시지 출처 표현 규칙을 구현한다.
- [x] 프론트엔드 모델 이력 선택을 방 단위 공유 기억으로 변경한다.
- [x] 백엔드 rolling summary 조회·생성을 공유 기억 기준으로 변경한다.
- [x] Observer 근거 제한과 문맥 전환 안내를 보강한다.
- [x] 프론트엔드·백엔드 테스트와 모듈 문서를 갱신한다.
- [x] 관련 테스트와 경계/UI audit를 실행한다.

## 검증
- 프론트엔드: 관련 Vitest로 일반 Chat→Observer, Observer→일반 Chat, Email RAG 격리를 확인한다.
- 백엔드: Docker Compose `api` 컨테이너에서 Assistant/Observer 관련 Django 테스트를 실행한다.
- 정적 점검: `npm run agent:audit:ui`, `npm run agent:audit:web-boundary`, `npm run agent:audit:api-boundary`를 실행한다.
- 기대 결과: 같은 방의 일반 Chat·Observer 이력과 장기 요약이 공유되고, Email RAG 및 다른 방은 섞이지 않는다.

## 위험과 대응
- 위험: 과거 Observer 분석을 현재 데이터의 사실처럼 재사용할 수 있다.
- 대응: Observer 프롬프트에서 현재 조회 JSON만 사실 근거로 허용하고 이전 대화는 배경 문맥으로 명시한다.
- 위험: 기존 문맥별 summary가 공유 summary와 중복될 수 있다.
- 대응: 새 공유 키만 조회·갱신하고 기존 row는 읽지 않아 동작 중복을 방지한다.
- 위험: 사용자 작업 중인 Observer 페이지 상태 파일과 충돌할 수 있다.
- 대응: 해당 두 파일은 수정·스테이징하지 않는다.

## 진행 기록
- 2026-08-12: 방 ID를 기억 경계로, `contextKey`를 라우팅·현재 근거 범위로 유지하는 설계를 확정했다.
- 2026-08-12: 일반 Chat↔Observer 양방향 최근 이력 공유와 Email RAG 격리 테스트를 추가했다.
- 2026-08-12: frontend 49개와 backend 44개 관련 테스트, migration check, UI/frontend/backend boundary audit를 통과했다.
