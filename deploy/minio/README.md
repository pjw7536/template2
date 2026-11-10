# MinIO 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

여러 앱이 함께 사용하는 독립 객체 저장소입니다. namespace는 `minio`이며 공용 Traefik을 먼저 준비합니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [이미지·계정·저장소·TLS·배포·파일 검증](docs/01-install.md) |
| 2 | [버킷 초기화 재시도·기존 데이터 이전·재생성](docs/02-operations.md) |

클러스터 내부 S3 SDK는 루트 주소 `http://minio.minio.svc.cluster.local:9000`을 사용합니다. 브라우저 파일 접근은 `https://s3.etch.samsungds.net/`을 사용합니다. 외부 S3 client의 서명 URL도 이 루트 endpoint로 생성합니다.
