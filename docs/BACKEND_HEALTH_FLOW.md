# Health 백엔드 로직 (feature: health)

## 개요
- 서비스 상태 확인용 헬스 체크 엔드포인트를 제공합니다.
- 인증/권한 없이 접근 가능합니다.

## 엔드포인트
- `GET /api/v1/health/`

## 상세 흐름
1. 요청 수신.
2. 고정된 JSON 반환: `{"status":"ok","application":"template2-api"}`

## 시퀀스 다이어그램
```mermaid
sequenceDiagram
    actor Client
    participant API as Health API

    Client->>API: GET /health/
    API-->>Client: {"status":"ok","application":"template2-api"}
```

## 관련 코드 경로
- `apps/api/api/health/views.py`
- `apps/api/api/health/urls.py`
