# VOC

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


VOC는 문의, 개선 요청, 답변을 관리하는 게시판형 기능입니다.

### 기능 요약

- 게시글 목록 조회
- 게시글 생성/수정/삭제
- SPA 목록 기준 상태별 카운트 계산
- 답변 작성
- ActivityLog 기록

### 게시글 상태

- `접수`
- `진행중`
- `완료`
- `반려`

### 권한

- 게시글 목록을 포함한 모든 API는 로그인과 Portal·`voc` 앱 접근이 필요합니다.
- 게시글 생성과 답변 작성은 앱 접근이 허용된 사용자가 수행합니다.
- 게시글 수정/삭제는 작성자 또는 VOC `admin`만 가능합니다.

### 처리 흐름

1. API가 게시글과 답변, 작성자를 canonical camelCase 형태로 반환합니다.
2. SPA가 받은 목록에서 상태·내 글 필터와 상태별 카운트를 계산합니다.
3. 생성/수정/삭제 시 ActivityLog metadata를 남깁니다.
4. 답변 작성 후 갱신된 게시글 정보를 반환합니다.

### 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/voc` |
| Frontend | `apps/portal/web/src/features/voc` |
| Backend API | `/api/v1/voc/posts`, `/api/v1/voc/posts/<post_id>`, `/api/v1/voc/posts/<post_id>/replies` |
| 데이터 | `VocPost`, `VocReply` |
| 부작용 | ActivityLog 기록 |

### 운영 포인트

- 상태별 카운트가 맞지 않으면 SPA의 현재 상태/내 글 필터와 `buildVocStatusCounts`를 확인합니다.
- 수정/삭제 403은 작성자 여부와 VOC `allowed/admin` 권한을 확인합니다.
- 답변 작성 후 목록 갱신은 React Query invalidation 범위를 확인합니다.

### 관련 API

- [VOC API](#api)

### 관련 코드

- `apps/portal/api/api/voc/views.py`
- `apps/portal/api/api/voc/models.py`
- `apps/portal/api/api/voc/selectors.py`
- `apps/portal/api/api/voc/serializers.py`
- `apps/portal/api/api/voc/services/posts.py`
- `apps/portal/web/src/features/voc`

## API


VOC API는 게시글과 답변을 관리합니다.

### 호출자

- 브라우저 SPA

### 인증

게시글 목록 조회를 포함한 모든 경로는 Django session과 Portal·`voc` 앱 접근이 필요합니다.

### Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/voc/posts` | 게시글 목록 |
| POST | `/api/v1/voc/posts` | 게시글 생성 |
| PATCH | `/api/v1/voc/posts/<post_id>` | 게시글 수정 |
| DELETE | `/api/v1/voc/posts/<post_id>` | 게시글 삭제 |
| POST | `/api/v1/voc/posts/<post_id>/replies` | 답변 작성 |

### 게시글 생성

```json
{
  "title": "문의 제목",
  "content": "문의 내용",
  "status": "접수"
}
```

허용 상태:

- `접수`
- `진행중`
- `완료`
- `반려`

### 응답 계약

목록 응답은 canonical camelCase 게시글 배열만 반환합니다.

```json
{
  "results": [
    {
      "id": 1,
      "title": "문의 제목",
      "content": "<p>문의 내용</p>",
      "status": "접수",
      "createdAt": "2026-08-01T00:00:00+00:00",
      "updatedAt": "2026-08-01T00:00:00+00:00",
      "author": { "id": 1, "name": "사용자(knox-id)" },
      "replies": []
    }
  ]
}
```

- 생성·수정 응답: `{ "post": VocPost }`
- 삭제 응답: `{ "success": true }`
- 답변 생성 응답: `{ "reply": VocReply, "post": VocPost }`
- `total`, `statusCounts`, snake_case/legacy 필드 별칭은 제공하지 않습니다.
- 상태·내 글 필터와 상태별 개수는 SPA가 받은 목록에서 계산합니다.
- 제거된 `app` 필드를 생성·수정 요청에 보내면 400 `invalid_request`와 `fieldErrors.app`을 반환합니다.

### 권한

- 게시글 수정/삭제: 작성자 또는 VOC `admin`
- 답변 작성: 인증 사용자

### 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 상태, 제거된 `app` 필드 또는 기타 입력 오류 |
| 401 | 로그인 필요 |
| 403 | 작성자 또는 VOC `admin` 권한 없음 |
| 404 | 게시글 없음 |

### 관련 모듈 문서

- [VOC 모듈](#기능과-흐름)
