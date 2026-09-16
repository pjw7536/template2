# ExecPlan: APP VIP의 두 Worker 443 연결

## 목표
- etch.samsungds.net → APP VIP 10.172.26.150 → 10.172.40.117:443, 10.172.40.87:443 연결을 지원한다.
- 기존 Keycloak·Airflow와 DB 위치를 유지하면서 두 Worker가 동일한 라우팅을 제공한다.

## 현재 상태
- 사용자 확인: SSH 불가 APP VIP이며 Backend 두 곳은 이미 443으로 등록됐다.
- 원본 Traefik은 etch-sso Deployment 하나, 단일 hostname nodeSelector, hostPort 80/443이다.
- server-up은 기존 namespace 감시를 보존하지만 단일 노드만 허용한다.

## 범위
- 공용 ingress 배치 함수, server-up/Make 입력, 회귀 테스트, 운영 문서.
- VIP·DNS·실제 클러스터와 Git remote는 이 외부 PC에서 변경하지 않는다.

## 설계
- NodePort를 추가하지 않는다. --vip-backends의 IPv4 목록을 클러스터 Node InternalIP로 해석한다.
- Traefik Deployment 이름은 유지하고 replicas=Backend 수, 필수 nodeAffinity/호스트 anti-affinity로 각 Worker 하나씩 배치한다.
- RollingUpdate maxSurge=0/maxUnavailable=1로 hostPort 충돌을 피하며 순서대로 교체한다.
- 적용한 Backend 목록은 Deployment annotation에 보존해 인자 없는 후속 server-up이 단일 노드로 되돌리지 않게 한다.
- IP 매핑·Ready/스케줄 가능·taint·기존 노드 유지·Pod hostPort 충돌을 쓰기 전에 검사한다.
- Airflow NODE_NAME은 기존 소스의 앱 Worker를 유지한다. 실제 URL·인증서는 Airflow env와 Secret으로 입력한다.

## 실행 단계
- [x] VIP 배치와 재실행 보존, 검사 전용 실행 구현
- [x] CLI/Make 연결, 두 Backend 포트 및 TLS 검증 절차 문서화
- [x] 정상·재실행·잘못된 IP/노드/포트 회귀와 기존 테스트 검증

## 검증
- 공유 Python 테스트와 실제 Kustomize를 입력한 배치 결과 확인
- 전체 Node 배포 회귀, Bash/Python 문법, 문서 감사, git diff --check
- 실클러스터 Pod 스케줄링·노드 OS 포트·VIP Health Check·TLS는 서버에서 확인해야 한다.

## 위험과 대응
- 단일 앱/DB Worker 장애는 VIP만으로 해결되지 않는다.
- LB TCP 443 Health Check가 실패한 Backend를 제외하도록 확인한다. 갱신 중 개별 연결은 재시도가 필요할 수 있다.
- 원본 정적 Keycloak apply는 단일 배치를 복원하므로 VIP 도입 후 server-up을 사용한다.

## 진행 기록
- 2026-09-15: 확정된 VIP와 Backend에 맞춰 hostPort 기반 두 Worker 배치를 준비한다.
- 2026-09-15: 공유 Python 18개와 실제 Kustomize 배치 검증을 포함한 전체 Node 회귀 46개 통과. Helm 3.19.0 checksum 확인 후 공식 chart 렌더와 make server-check APP=keycloak-airflow 통과.
- 2026-09-15: Python 문법·문서 감사·git diff --check 통과. 실제 클러스터 스케줄링·VIP 연결·사내 인증서는 외부 PC에서 검증하지 않았다. commit/push와 서버 적용도 수행하지 않았다.
