# 사내 이미지 저장소(Zot) 배포

[전체 배포](../README.md) · [공통 준비](../shared/docs/README.md)

## 역할

사내에서 빌드한 이미지를 보관하고 각 노드의 containerd가 내려받게 하는 OCI registry입니다.
namespace는 `registry`이며 지정 Worker 한 대에서 실행합니다. 외부 공개 이미지는 계속 사내 Nexus 미러에서 받습니다.

- push: 빌드 host(`khinfow01`)가 htpasswd 계정으로 로그인한 뒤 업로드
- pull: 각 노드 containerd가 익명으로 내려받음
- 접속: 공용 Traefik HTTPS entrypoint의 `REGISTRY_HOST`

## 의존 서비스

| 대상 | 필요한 것 |
| --- | --- |
| 공용 Traefik | `etch-sso/traefik`, APP VIP 443 전달, `REGISTRY_HOST`용 공용 TLS 인증서. `registry` namespace 감시는 배포 스크립트가 추가합니다 |
| DNS | `REGISTRY_HOST` → 공용 APP VIP |
| Kubernetes | `NODE_NAME` Worker, local PV용 `DATA_HOST_PATH` 폴더 |
| 이미지 | [env/k8s.env](env/k8s.env)의 Zot 이미지를 Worker가 받을 수 있는 사내 ghcr.io 미러 |
| 각 노드·빌드 host | 사내 루트 CA 신뢰 |

## 설치 순서

| 순서 | 문서 |
| --- | --- |
| 1 | [폴더·계정·배포·노드 설정·검증](docs/01-install.md) |
| 2 | [이미지 push·정리·계정 교체·주소 전환](docs/02-operations.md) |

## 완료 기준

PVC `Bound`, Deployment `Available`이고, 빌드 host에서 테스트 이미지 push와 다른 노드에서 `crictl pull`이 성공합니다.

## 접속 경로와 운영 정보

- 노드·빌드 host: `https://<REGISTRY_HOST>/v2/`, 이미지 이름 `<REGISTRY_HOST>/<이름>:<tag>`
- 웹 화면: `https://<REGISTRY_HOST>/` (익명 조회)

실제 주소·배치·저장소 연결은 [서비스 접속 주소](../shared/docs/infrastructure/services.md#서비스-접속-주소)와 [앱별 배치와 스토리지 선언](../shared/docs/infrastructure/services.md#앱별-배치와-스토리지-선언)에서 관리합니다.
