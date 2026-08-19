# VOC 모듈

VOC는 문의, 개선 요청, 답변을 관리하는 게시판형 기능입니다.

## 기능 요약

- 게시글 목록 조회
- 게시글 생성/수정/삭제
- SPA 목록 기준 상태별 카운트 계산
- 답변 작성
- ActivityLog 기록

## 게시글 상태

- `접수`
- `진행중`
- `완료`
- `반려`

## 권한

- 게시글 생성과 답변 작성은 인증 사용자가 수행합니다.
- 게시글 수정/삭제는 작성자 또는 VOC `admin`만 가능합니다.

## 처리 흐름

1. API가 게시글과 답변, 작성자를 canonical camelCase 형태로 반환합니다.
2. SPA가 받은 목록에서 상태·내 글 필터와 상태별 카운트를 계산합니다.
3. 생성/수정/삭제 시 ActivityLog metadata를 남깁니다.
4. 답변 작성 후 갱신된 게시글 정보를 반환합니다.

## 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/voc` |
| Frontend | `apps/web/src/features/voc` |
| Backend API | `/api/v1/voc/posts`, `/api/v1/voc/posts/<post_id>`, `/api/v1/voc/posts/<post_id>/replies` |
| 데이터 | `VocPost`, `VocReply` |
| 부작용 | ActivityLog 기록 |

## 운영 포인트

- 상태별 카운트가 맞지 않으면 SPA의 현재 상태/내 글 필터와 `buildVocStatusCounts`를 확인합니다.
- 수정/삭제 403은 작성자 여부와 VOC `allowed/admin` 권한을 확인합니다.
- 답변 작성 후 목록 갱신은 React Query invalidation 범위를 확인합니다.

## 관련 API

- `docs/api/voc.md`

## 관련 코드

- `apps/api/api/voc/views.py`
- `apps/api/api/voc/models.py`
- `apps/api/api/voc/selectors.py`
- `apps/api/api/voc/serializers.py`
- `apps/api/api/voc/services/posts.py`
- `apps/web/src/features/voc`
