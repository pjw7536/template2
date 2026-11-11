# MinIO 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

여러 앱이 함께 사용하는 독립 S3 호환 객체 저장소입니다. namespace는 `minio`이며 지정 Worker 한 대에서 실행합니다.
앱별 접근 키·버킷 정책은 각 앱 env에서 관리합니다.

## 의존 서비스

| 대상 | 필요한 것 |
| --- | --- |
| 공용 Traefik | `etch-sso/traefik`과 `MINIO_API_HOST`·`MINIO_CONSOLE_HOST` 두 host의 TLS 등록 |
| Kubernetes | `NODE_NAME` Worker, 신규 local PV 또는 동적 StorageClass, hostPath 준비 Job 허용 |
| 이미지 | [env/prod.env](env/prod.env)의 MinIO 서버·mc 이미지를 Worker가 받을 수 있는 사내 미러 |

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [입력·이미지·저장소·TLS·배포·검증](docs/01-install.md) |
| 2 | [버킷 초기화 재시도·기존 namespace 이전·재생성](docs/02-operations.md) |

## 완료 기준

PVC `Bound`, Deployment `Available`, `minio-init` Job `Complete`이고 콘솔 로그인과 테스트 파일 업로드·다운로드가 성공합니다.

## 접속 경로와 운영 정보

- 클러스터 내부 S3 SDK: `http://minio.minio.svc.cluster.local:9000`
- 외부 S3 client·브라우저 파일 접근: `MINIO_API_HOST`의 HTTPS 루트, 콘솔: `MINIO_BROWSER_REDIRECT_URL`

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.
