# VOC API

VOC API는 게시글과 답변을 관리합니다.

## 호출자

- 브라우저 SPA

## 인증

게시글 생성, 수정, 삭제, 답변 작성에는 Django session이 필요합니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/voc/posts` | 게시글 목록 |
| POST | `/api/v1/voc/posts` | 게시글 생성 |
| PATCH | `/api/v1/voc/posts/<post_id>` | 게시글 수정 |
| DELETE | `/api/v1/voc/posts/<post_id>` | 게시글 삭제 |
| POST | `/api/v1/voc/posts/<post_id>/replies` | 답변 작성 |

## 게시글 생성

```json
{
  "title": "문의 제목",
  "content": "문의 내용",
  "status": "접수",
  "app": "기타"
}
```

허용 상태:

- `접수`
- `진행중`
- `완료`
- `반려`

## 응답 계약

목록 응답은 canonical camelCase 게시글 배열만 반환합니다.

```json
{
  "results": [
    {
      "id": 1,
      "title": "문의 제목",
      "content": "<p>문의 내용</p>",
      "status": "접수",
      "app": "기타",
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
- 상태·앱·내 글 필터와 상태별 개수는 SPA가 받은 목록에서 계산합니다.

## 권한

- 게시글 수정/삭제: 작성자 또는 VOC `admin`
- 답변 작성: 인증 사용자

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 잘못된 상태 또는 입력 |
| 401 | 로그인 필요 |
| 403 | 작성자 또는 VOC `admin` 권한 없음 |
| 404 | 게시글 없음 |

## 관련 모듈 문서

- `docs/modules/voc.md`
