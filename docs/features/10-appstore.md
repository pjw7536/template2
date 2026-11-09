# AppStore

[문서 홈](../README.md) · [기능·API](README.md)

- [기능과 흐름](#기능과-흐름)
- [API](#api)

## 기능과 흐름


AppStore는 내부 앱과 도구를 등록하고 공유하는 기능입니다.

### 기능 요약

- 앱 목록/상세 조회
- 앱 등록/수정/삭제
- 관리자 전용 앱 노출 순서 관리
- 대표 이미지 제공
- 앱 좋아요/조회수
- 댓글/대댓글
- 댓글 좋아요

### 권한

- 조회·대표 이미지·댓글을 포함한 모든 API는 로그인과 Portal·`appstore` 앱 접근이 필요합니다.
- 앱 등록, 좋아요, 댓글 작성은 앱 접근이 허용된 사용자가 수행합니다.
- 앱 수정/삭제는 작성자 또는 Appstore `admin`만 가능합니다.
- 앱 노출 순서 변경은 Appstore `admin`만 가능합니다.
- 댓글 수정/삭제는 작성자 또는 Appstore `admin`만 가능합니다.

### 앱 등록 흐름

1. 사용자가 앱 이름, URL, 설명, 카테고리, 스크린샷을 제출합니다.
2. 서버가 필수값과 길이를 검증합니다.
3. 스크린샷을 대표 이미지와 gallery로 정리합니다.
4. 앱을 저장하고 payload를 반환합니다.

### 대표 이미지

대표 이미지가 URL이면 redirect하고, base64/data URL이면 이미지 바이너리로 응답합니다.

### 앱 노출 순서

- 앱 카드는 DB에 저장된 전역 노출 순서대로 표시됩니다.
- Appstore `admin`은 카드 grid의 순서 편집 모드에서 전체 또는 선택 카테고리의 앱을 drag-and-drop하고 일괄 저장할 수 있습니다.
- 카테고리 내 정렬은 해당 카테고리 앱들이 차지한 전역 `display_order` 슬롯만 교체하므로 다른 카테고리 앱의 위치를 유지합니다.
- 신규 앱은 기존 순서를 유지하면서 마지막에 추가됩니다.
- 검색과 카테고리 필터는 전역 순서의 상대적 순서를 유지합니다.
- 동시 편집 또는 앱 추가/삭제 충돌이 감지되면 최신 목록을 다시 조회합니다.

### 화면/API/데이터 추적

| 구간 | 위치 |
| --- | --- |
| 화면 | `/appstore` |
| Frontend | `apps/portal/web/src/features/appstore` |
| Backend API | `/api/v1/appstore/**` |
| 데이터 | `AppStoreApp`, `AppStoreLike`, `AppStoreComment`, `AppStoreCommentLike` |
| 파일/이미지 | cover endpoint가 URL redirect 또는 이미지 바이너리를 반환 |

### 운영 포인트

- 이미지가 깨지면 cover URL/data URL 형식과 `/cover` 응답 방식을 확인합니다.
- 수정/삭제 403은 작성자 여부와 Appstore `allowed/admin` 권한을 확인합니다.
- 댓글/좋아요 불일치는 앱/댓글 ID와 로그인 사용자 기준 중복 여부를 확인합니다.

### 관련 API

- [AppStore API](#api)

### 관련 코드

- `apps/portal/api/api/appstore/views/`
- `apps/portal/api/api/appstore/models.py`
- `apps/portal/api/api/appstore/selectors.py`
- `apps/portal/api/api/appstore/serializers.py`
- `apps/portal/api/api/appstore/services/apps.py`
- `apps/portal/api/api/appstore/services/comments.py`
- `apps/portal/api/api/appstore/services/likes.py`
- `apps/portal/api/api/appstore/services/screenshots.py`
- `apps/portal/web/src/features/appstore`

## API


AppStore API는 내부 앱 등록, 조회, 댓글, 좋아요 기능을 제공합니다.

### 호출자

- 브라우저 SPA

### 인증

- 목록·상세·대표 이미지·댓글 GET을 포함한 모든 경로는 세션 인증과 Portal·`appstore` 앱 접근이 필요합니다.
- 수정·삭제·순서 편집에는 아래 작성자·관리자 조건을 추가로 검사합니다.

### Endpoint

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

### 앱 등록 요청

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

### 권한

- 앱 수정/삭제: 작성자 또는 Appstore `admin`
- 앱 노출 순서 변경: Appstore `admin`
- 댓글 수정/삭제: 작성자 또는 Appstore `admin`
- 좋아요: 로그인 사용자

### 앱 목록과 노출 순서

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

### 오류

| Status | 상황 |
| --- | --- |
| 400 | 필수값 누락 또는 잘못된 이미지 |
| 401 | 로그인 필요 |
| 403 | 작성자 또는 Appstore `admin` 권한 없음 |
| 404 | 앱 또는 댓글 없음 |
| 409 | 순서 편집 이후 앱 목록 또는 노출 순서가 변경됨 |

### 관련 모듈 문서

- [AppStore 모듈](#기능과-흐름)
