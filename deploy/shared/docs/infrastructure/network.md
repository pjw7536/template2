# 네트워크·VIP·DNS

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

클러스터·업무 네트워크 주소와 연결 관계의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
담당자는 미확인입니다. 접속 경로의 확인 범위와 남은 확인은 아래 항목을 따릅니다.

## VIP·DNS·접속 경로

| 용도 | 주소·연결 | 근거·확인 상태 |
| --- | --- | --- |
| Kubernetes API VIP | `10.172.26.148:6443` | API 접속점. 실제 kubeconfig·가입 endpoint·LB backend 확인 필요 |
| 업무 서비스 APP VIP | `10.172.26.150:443` | 사용자 확인: 인프라팀 발급, SSH 접근 대상 아님. 현재 LB·HTTPS 응답 확인 필요 |
| 업무 DNS → APP VIP | `etch.samsungds.net` → `10.172.26.150` | 사용자 확인: DNS 연결. 현재 DNS 응답·인증서 확인 필요 |
| APP VIP backend 1 | `10.172.40.117:443` → `khplanew01` | 사용자 확인: LB backend·노드 대응. 현재 backend·Traefik 응답은 재조회 |
| APP VIP backend 2 | `10.172.40.87:443` → `khplane01w09` | 사용자 확인: LB backend·노드 대응. 현재 backend·Traefik 응답은 재조회 |
| HTTPS 연결 | APP VIP → Worker hostPort 443 → 공용 Traefik → 앱 Service | [VIP 절차](../../ingress/01-VIP.md)의 목표 구성. TLS는 Traefik에서 종료하며 실제 LB 전달 방식·PROXY protocol 사용 여부 확인 필요 |

Keycloak DNS의 실제 연결 대상과 APP VIP 적용 여부는 미확인입니다. Worker 직결 여부와 함께 조회합니다.
새 검증 환경에는 운영 IP를 재사용하지 않습니다.

## FTP 직접 접속

아래는 `deploy/ftp/k8s/stack.yaml`의 노드 직접 연결에 필요한 조건입니다.
실제 방화벽 개방·노드별 연결 성공·담당자는 미확인입니다.

| 출발지 | 목적지 | TCP 포트 | 용도·남은 확인 |
| --- | --- | --- | --- |
| 파일 전송 클라이언트의 허용 IP/CIDR | 선택한 FTP 노드의 InternalIP | `6380` | FTP 제어·로그인. 실제 출발지·대상 노드·방화벽 승인 확인 필요 |
| 같은 허용 출발지 | 같은 FTP 노드 InternalIP | `8076–8079` | Passive 목록·업로드·다운로드. 호스트·중간 방화벽과 실제 전송 확인 필요 |

FTP는 `hostNetwork`를 사용하고 Passive 주소에는 해당 노드의 `status.hostIP`를 전달합니다.
업무 APP VIP·Traefik을 경유하지 않는 노드 직접 연결입니다. 현재 절차는 IPv4 InternalIP 직접 접근을 전제하며 NAT·TLS는 별도 설정이 필요합니다.
`FTP_NODES`에 명시한 control plane도 기본적으로 FTP 대상에 포함할 수 있습니다. 접속 경로는 노드별 직접 수신입니다.
노드명·IP는 [서버 목록](servers.md), 배치·데이터는 [FTP 서비스](services.md#ftp-노드별-파일-수신), 실행 방법은 [FTP 설치](../../../ftp/01_SERVER_SETUP.md)를 따릅니다.

## 클러스터 네트워크·실행 기반

| 항목 | 확인 상태·근거 | 남은 확인 |
| --- | --- | --- |
| CNI·Pod/Service CIDR·MTU·DNS domain | 미확인. 구축 기록·각 노드·시스템 리소스 조회 필요 | 네트워크 담당자 확인, Worker 가입·Pod/Service 통신 검증 |

## 추가 확인·변경 연계

| 대상 | 확인할 정보 | 현재 상태 |
| --- | --- | --- |
| 네트워크 접근 | 방화벽 허용 방향·포트·접속 경유지·담당자 | 미확인 |
| VIP·DNS | 기록된 backend·노드 대응·DNS의 최신 상태와 TLS 종료 위치 | 최신 조회 필요 |

VIP backend 변경 시 [서버 목록](servers.md), 공개 URL 변경 시 [서비스 주소](services.md), TLS 입력 변경 시 [인증서 관리](../../certs/README.md)를 대조합니다.
조회·실행 절차는 [현재 환경 확인](../kubernetes/09-baseline.md)과 [VIP 적용](../../ingress/01-VIP.md)을 따릅니다.
