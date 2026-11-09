# FTP 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

선택한 Linux 노드마다 FTP Pod를 실행합니다. 파일은 접속한 노드에만 저장되며 노드 사이에 복제되지 않습니다.

| 순서 | 작업 |
| --- | --- |
| 1 | [노드·포트·계정 준비와 배포](docs/01-install.md) |
| 2 | [송수신 확인·노드·계정 변경·장애 대응](docs/02-operations.md) |
| 3 | [이미지·경로를 변경하는 수동 overlay](docs/03-kubernetes.md) |

노드 IP의 6380과 passive 포트 8076–8079로 직접 접속합니다. control plane 선택은 `FTP_ALLOW_CONTROL_PLANE`로 제어합니다.
