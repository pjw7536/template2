# 공용 MinIO 설치 안내

MinIO는 Portal에서 분리되었습니다. 독립 설치는 [공용 MinIO 설치·운영](../minio/README.md)을 따릅니다.

- 배포 설정: `deploy/minio`, 운영 namespace: `minio`
- 설치 명령: `make minio-check`, `make minio-up`
- 콘솔 주소: `https://etch.samsungds.net/minio-console/`
- Portal API의 S3 주소: `http://minio.minio.svc.cluster.local:9000`

이전 `tailwind-internal` 설치가 있으면 새 안내의 기존 데이터 이전 절차를 먼저 확인합니다.
기존 PVC·PV·데이터는 자동으로 옮기거나 삭제하지 않습니다.
