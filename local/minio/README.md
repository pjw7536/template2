# 로컬 공용 MinIO

`deploy/minio/k8s/base`를 재사용합니다. 서버 입력은 `env/minio.env`에 있습니다.
기존 개발 데이터 보존을 위해 namespace `tailwind-local`, PVC `minio-data`, PV `tailwind-local-minio`,
호스트 마운트 `/data/local-runtime/minio`는 유지합니다.

전체 실행은 `make dev`, MinIO 갱신은 `make k8s-rebuild APP=minio`입니다.
콘솔은 `http://localhost:8080/minio-console/`, 파일 경로는 `/minio/`입니다.
사내 이미지 주소는 사용하지 않으며 local/shared의 `LOCAL_MINIO_IMAGE`, `LOCAL_MINIO_CLIENT_IMAGE`로 이미지를 지정합니다.
