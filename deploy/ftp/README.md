# FTP 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

선택한 Linux 노드마다 DaemonSet으로 FTP Pod 하나를 실행합니다. 클라이언트는 각 노드 InternalIP의 TCP 6380과 passive 포트 8076–8079로 직접 접속합니다.
파일은 접속한 노드의 `/appdata/data_movement`에만 저장되며 노드 사이에 복제되지 않습니다. Service·Ingress·VIP는 만들지 않습니다.

## 의존 서비스

| 대상 | 필요한 것 |
| --- | --- |
| Kubernetes | 대상 노드 등록·Ready, `hostNetwork`·`hostPath`를 허용하는 namespace 정책 |
| 네트워크 | 클라이언트 → 각 FTP 노드 InternalIP의 TCP 6380, 8076–8079 방화벽 개방 |
| 이미지 | [env/prod.env](env/prod.env)의 `FTP_IMAGE`를 Worker가 받을 수 있는 사내 미러 |

Portal·Keycloak·공용 Traefik 없이 설치할 수 있습니다. control plane 선택은 `FTP_ALLOW_CONTROL_PLANE`로 제어합니다.

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [노드·포트·계정 준비와 배포](docs/01-install.md). 기본 배포 또는 [별도 overlay 배포](docs/01-install.md#별도-overlay-배포) 중 하나를 사용합니다. |
| 2 | [송수신 확인·노드·계정 변경·장애 대응](docs/02-operations.md) |

## 완료 기준

선택한 모든 노드에 FTP Pod가 하나씩 Ready이고, 각 노드 IP로 passive 모드 로그인·업로드·다운로드가 성공하며, 파일이 접속한 노드의 `/appdata/data_movement`에만 생깁니다.

## 운영 정보

대상 노드·접속 주소·검증 결과는 [FTP 서비스 기록](../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신), 방화벽은 [FTP 네트워크 기록](../shared/docs/infrastructure/network.md#ftp-직접-접속)에서 관리합니다.
