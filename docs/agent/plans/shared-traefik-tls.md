# ExecPlan: 공용 Traefik TLS 관리

## 목표
- 업무 서비스와 SSO 인증서를 공용 Traefik namespace에서 한 번만 관리한다.
- 앱 namespace에 TLS Secret을 복제하지 않고 기존 HTTPS 주소와 경로를 유지한다.

## 현재 상태
- 공용 Traefik은 etch-sso에서 Kubernetes Ingress와 file provider를 사용한다.
- 각 앱은 별도 TLS Secret을 요구하며 Airflow는 기존 Secret을 복제한다.

## 범위
- deploy/shared의 인증서 등록·검사, 각 앱의 Ingress 및 배포 사전 검사, 관련 env·문서·검증.
- 앱 인증 방식, CA 신뢰 설정, DNS, VIP와 저장 데이터는 변경하지 않는다.

## 설계
- etch-sso/traefik-tls Opaque Secret에 도메인별 PEM과 file provider 설정을 함께 저장한다.
- 기존 middleware ConfigMap과 선택적 TLS Secret을 같은 디렉터리에 projected volume으로 마운트한다.
- Traefik은 SNI로 인증서를 선택하고 앱은 websecure와 router.tls만 선언한다.
- 등록 도구는 파일 또는 기존 namespace/Secret을 받아 호스트·유효기간·개인키를 검사한다.
- 갱신 시 다른 도메인과 metadata를 보존하고 resourceVersion으로 동시 변경을 차단한다.
- 기존 앱별 인증서는 자동 삭제하지 않는다. 공용 등록 후 ingress-up, 앱 재배포 순서로 이전한다.
- 기존 TLS env 키는 빈 값으로 전환하며 이전 env도 읽을 수 있게 호환한다. Keycloak도 기본 배포에서는 공용 인증서를 검사하고 PEM을 다시 등록하지 않는다.

## 실행 단계
- [x] 공용 등록·검사 도구와 Traefik 마운트 추가
- [x] 앱 Ingress와 배포 검사·기존 입력 호환 정리
- [x] 운영 문서·env·export 동기화
- [x] 단위 검사·전체 렌더·실제 Traefik SNI 검증

## 검증
- 공용 TLS 검사: 실제 임시 PEM을 사용해 잘못된 호스트·키, 만료, 갱신 보존·충돌 확인.
- 앱별 Python 검사와 관련 Node 배포·선택 checkout 검사.
- make server-check APP=all PROFILE=prod, env-profile-key-check, k8s-check.
- Docker Traefik으로 두 도메인 인증서 선택과 갱신 확인. 사내 클러스터에는 적용하지 않는다.

## 위험과 대응
- 잘못된 인증서: 적용 전 openssl 검사, 민감값은 stdin으로만 전달.
- 기존 앱 HTTPS 중단: 인증서를 먼저 공용 등록하고 controller 갱신 후 앱을 전환한다.
- Secret 볼륨 갱신 감지: 인증서 등록 도구에서 기존 Traefik을 재시작하고 rollout 확인.
- 기존 VIP·감시 namespace: 기존 공용 배치 보존 도구를 그대로 사용한다.

## 진행 기록
- 2026-10-28: 현재 구조와 Traefik 공식 file provider·SNI 계약을 확인하고 계획 작성.

- 2026-10-28: 공용 TLS 도구·projected 마운트와 6개 앱의 HTTPS 참조를 전환했다. Keycloak 기본 배포의 PEM 재등록을 제거하고 기존 명시 입력만 호환했다.
- 2026-10-28: 배포 Python 187개(shared 94, MinIO 12, Airflow 46, Headlamp 15, Monitoring 20), local runtime 5개, 관련 Node 86개로 총 278개 검사 통과. Helm 설치 환경에서 skip 없이 실행했다.
- 2026-10-28: `make server-check APP=all PROFILE=prod`, `make env-profile-key-check`, `make k8s-check`, `git diff --check` 통과. `make k8s-export`로 전달 YAML을 재생성했다.
- 2026-10-28: Keycloak·Portal·Airflow·Headlamp·Monitoring·MinIO의 총 9개 Ingress를 실제 Kustomize/Helm/env로 렌더해 HTTPS annotation 유지와 앱별 TLS Secret 참조 제거를 확인했다.
- 2026-10-28: Docker Traefik v3.7.1에 임시 인증서 2개와 저장소의 TLS 설정·MinIO middleware를 로드했다. Kubernetes projected volume 형태의 symlink를 재현해 업무/SSO SNI 선택, 업무 인증서 갱신·재시작 후 새 지문 제공, SSO 지문 보존을 확인했다. 실제 앱 backend 대신 noop 응답을 사용했으며 사내 인증서·VIP·클러스터는 검증하지 않았다. 임시 컨테이너·PEM은 정리했다.
- 2026-10-28: 사내 클러스터 적용과 Git 커밋·push는 수행하지 않았다. 실제 운영은 공용 인증서 등록 → ingress-up → 사용하는 앱 재배포 후 HTTPS 확인 순서로 진행한다.
- 2026-10-28: 사용자 요청으로 현재 변경 54개 파일의 main 반영을 준비했다. 원격 main과 기준 커밋이 같음을 확인했고 검사 278개·서버 전체 검사·env 계약 검사·로컬 Kubernetes 렌더 검사를 다시 통과했다. 사내 클러스터 적용은 이번 Git 마무리에 포함하지 않는다.
