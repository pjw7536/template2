# AppStore API

AppStore API는 내부 앱 등록, 조회, 댓글, 좋아요 기능을 제공합니다.

## 호출자

- 브라우저 SPA

## 인증

- 목록/상세 조회는 비로그인 접근도 일부 허용될 수 있습니다.
- 등록, 수정, 삭제, 좋아요, 댓글 작성은 로그인 사용자가 필요합니다.

## Endpoint

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/v1/appstore/apps` | 앱 목록 |
| POST | `/api/v1/appstore/apps` | 앱 등록 |
| PUT | `/api/v1/appstore/apps/order` | 앱 노출 순서 일괄 변경(Appstore admin) |
| GET | `/api/v1/appstore/apps/<app_id>` | 앱 상세 |
| PATCH | `/api/v1/appstore/apps/<app_id>` | 앱 수정 |
| DELETE | `/api/v1/appstore/apps/<app_id>` | 앱 삭제 |
| GET | `/api/v1/appstore/apps/<app_id>/cover` | 대표 이미지 |
| POST | `/api/v1/appstore/apps/<app_id>/like` | 앱 좋아요 토글 |
| POST | `/api/v1/appstore/apps/<app_id>/view` | 조회수 증가 |
| GET | `/api/v1/appstore/apps/<app_id>/comments` | 댓글 목록 |
| POST | `/api/v1/appstore/apps/<app_id>/comments` | 댓글 작성 |
| PATCH | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>` | 댓글 수정 |
| DELETE | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>` | 댓글 삭제 |
| POST | `/api/v1/appstore/apps/<app_id>/comments/<comment_id>/like` | 댓글 좋아요 토글 |

## 앱 등록 요청

```json
{
  "name": "업무 도구",
  "category": "Tools",
  "description": "설명",
  "url": "https://example.com",
  "manualUrl": "https://example.com/manual",
  "screenshotUrls": ["https://example.com/cover.png"],
  "coverScreenshotIndex": 0,
  "contactName": "홍길동",
  "contactKnoxid": "hong"
}
```

## 권한

- 앱 수정/삭제: 작성자 또는 Appstore `admin`
- 앱 노출 순서 변경: Appstore `admin`
- 댓글 수정/삭제: 작성자 또는 Appstore `admin`
- 좋아요: 로그인 사용자

## 앱 목록과 노출 순서

앱 목록은 관리자가 저장한 `displayOrder` 오름차순으로 반환됩니다. 동일 값은 앱 `id` 오름차순으로 안정적으로 정렬됩니다.

```json
{
  "results": [
    {
      "id": 12,
      "name": "업무 도구",
      "displayOrder": 1
    }
  ],
  "total": 1,
  "orderVersion": "opaque-version",
  "permissions": {
    "canReorder": true
  }
}
```

순서를 변경할 때는 목록 응답의 전체 앱 ID와 `orderVersion`을 함께 전송합니다.

```json
{
  "appIds": [12, 7, 31],
  "orderVersion": "opaque-version"
}
```

- 신규 앱은 현재 노출 순서의 마지막에 추가됩니다.
- 편집 이후 앱 목록이나 순서가 바뀌면 `409`를 반환하므로 목록을 다시 조회해야 합니다.
- 일부 앱만 보내거나 중복 ID를 보내면 저장되지 않습니다.

## 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수값 누락 또는 잘못된 이미지 |
| 401 | 로그인 필요 |
| 403 | 작성자 또는 Appstore `admin` 권한 없음 |
| 404 | 앱 또는 댓글 없음 |
| 409 | 순서 편집 이후 앱 목록 또는 노출 순서가 변경됨 |

## 관련 모듈 문서

- `docs/modules/appstore.md`
