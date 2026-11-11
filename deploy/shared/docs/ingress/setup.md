# Traefik 셋업

[가이드 홈](../README.md#https인증서) · [Worker 추가](../kubernetes/worker.md) · [운영 기준](operations.md) · [Traefik·VIP 확장](expand.md)

**목적:** 앱들이 함께 사용하는 HTTPS 진입점(공용 Traefik)을 저장소 원본으로 설치하거나 갱신합니다.

```text
브라우저 → APP VIP:443 → Traefik이 있는 Worker:443 → 앱 Service → 앱 Pod
```

- APP VIP는 외부 요청용이며 Kubernetes 관리용 API VIP와 구분합니다. 현재 주소·backend는 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)을 따릅니다.
- LB가 TCP 443을 Worker에 전달하고 Traefik이 TLS를 종료하는 구성을 기준으로 합니다. TLS offloading·PROXY protocol을 쓴다면 LB와 Traefik 입력을 함께 확인합니다.
- 앱 Pod는 Traefik과 다른 Worker에 있어도 클러스터 네트워크로 연결됩니다. backend 추가가 앱·DB 복제를 뜻하지 않습니다.

**어느 문서를 쓰나요?**

| 상황 | 절차 |
| --- | --- |
| 최초 설치, 저장소 원본(이미지·인자)으로 갱신하면서 backend 지정 | 이 문서 1~5 |
| backend 변경 없이 원본만 갱신 | [대상 변경 없는 갱신](#대상-변경-없는-갱신) |
| 운영 중인 Traefik의 이미지·인자를 유지한 채 backend만 추가하고 복구 파일이 필요 | [Traefik·VIP 확장](expand.md) |

**준비물:**

- Traefik을 배치할 Ready Worker 최소 한 대. 없으면 [Worker 추가](../kubernetes/worker.md)를 먼저 진행합니다.
- CP1 배포 계정의 [배포 도구](../kubernetes/prerequisites.md#3-배포-도구--cp1)와 [CP1 저장소](../operations/01-checkout.md#저장소-clone)
- 사용할 공개 도메인의 fullchain PEM과 짝이 맞는 개인키, 또는 기존 TLS Secret

**실행 위치:** CP1의 저장소 루트. 이 명령은 `deploy/shared`와 루트 Makefile만 사용하며 앱 env·소스·local 파일을 읽지 않습니다.

## 1. 배포 대상·포트 검사 — CP1·선택한 Worker

```bash
kubectl config get-contexts
read -r -p '서버 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-sso get deployment traefik --ignore-not-found
read -r -p 'Traefik을 배치할 전체 Worker IP 목록(쉼표 구분): ' VIP_BACKENDS
export VIP_BACKENDS
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
```

- `VIP_BACKENDS`에는 LB에 연결할 **기존 Worker와 새 Worker IP 전체**를 넣습니다. 기존 backend를 빼고 적용하지 않습니다.
- `ingress-check`는 공통 원본·노드 Ready·cordon·taint·선언된 80/443 hostPort 충돌을 검사하며 클러스터를 변경하지 않습니다.

**기대 결과:** `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`

**실패 확인:** 표시된 노드·IP·포트 충돌 또는 기존 backend 누락을 해결한 뒤 다시 검사합니다. 검사 실패 상태로 2단계 이후를 진행하지 않습니다.

선택한 각 Worker에서 OS 프로세스의 포트 점유도 확인합니다.

```bash
sudo ss -lntp '( sport = :80 or sport = :443 )'
```

Nginx 등 다른 프로세스가 점유 중이면 담당자와 조정하며 자동으로 종료하지 않습니다.
hostPort는 네트워크 규칙으로 구현될 수 있으므로 ss 출력이 비어 있어도 Traefik이 실행 중일 수 있습니다.

## 2. TLS 인증서 등록 — CP1

필요한 공개 도메인마다 반복합니다. 파일 준비·추출은 [인증서 원본 준비](../certificates/prepare.md)부터 시작합니다.

```bash
read -r -p '공개 도메인: ' TLS_HOST
read -r -p 'fullchain PEM 절대 경로: ' TLS_CERT_FILE
read -r -p 'PEM 개인키 절대 경로: ' TLS_KEY_FILE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$TLS_HOST" \
  TLS_CERT_FILE="$TLS_CERT_FILE" TLS_KEY_FILE="$TLS_KEY_FILE"
```

기존 TLS Secret에서 가져올 때는 [인증서 적용](../certificates/apply.md#2-공용-tls-secret-등록갱신--cp1)의 `TLS_SOURCE` 방식을 사용합니다.

**기대 결과:** `공용 TLS 등록 완료`가 표시되고 인증서가 공용 `etch-sso/traefik-tls`에 등록됩니다.
도구가 도메인·만료·키 일치를 검사하며 다른 도메인의 인증서는 유지합니다.

## 3. Traefik 설치·갱신 — CP1

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
kubectl --context "$KUBE_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

`ingress-up`은 `etch-sso` namespace와 공용 리소스를 준비하며 Keycloak·DB·다른 앱을 재배포하지 않습니다.

**기대 결과:** `공용 Ingress 준비 완료`가 표시되고 대상 Worker마다 Traefik이 하나씩 `1/1 Running`입니다.

**실패 확인:**

| 상태 | 먼저 확인할 내용 |
| --- | --- |
| Pending | `kubectl describe pod`의 이벤트 |
| ImagePullBackOff | 해당 노드의 이미지 미러·인증 |
| Ready 실패 | Pod 로그와 CNI 연결 |

## 4. Worker 직접 → APP VIP 검증 — CP1·인프라 담당자

처음 설치했다면 앱 Ingress를 연결한 뒤 실제 앱의 정상 경로를 사용합니다. 기존 서비스가 있으면 그 경로로 바로 검사합니다.
사내 CA가 신뢰 저장소에 없으면 curl에 `--cacert`를 추가합니다.

```bash
read -r -p '검사할 공개 도메인: ' CHECK_HOST
read -r -p '정상 응답을 확인할 앱 경로(/로 시작): ' CHECK_PATH
read -r -p '직접 검사할 Worker IP: ' CHECK_WORKER_IP
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$CHECK_HOST:443:$CHECK_WORKER_IP" "https://$CHECK_HOST$CHECK_PATH"
```

모든 대상 Worker의 직접 요청이 성공한 뒤 인프라 담당자가 새 LB backend를 활성화하고 Health Check가 UP인지 확인합니다. 그다음 VIP를 검사합니다.

```bash
read -r -p 'APP VIP: ' APP_VIP
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$CHECK_HOST:443:$APP_VIP" "https://$CHECK_HOST$CHECK_PATH"
```

**실패 확인:** 앱이 아직 없는 `/`의 404만으로 Traefik 장애라고 판단하지 않습니다. 한 번의 VIP 성공만으로 모든 backend가 정상이라고 판단하지 않습니다.

## 5. 완료 기준과 다음 단계

대상 Traefik Ready → 각 Worker의 실제 앱 HTTPS 정상 → LB backend UP → VIP·DNS로 앱 접속 정상.

- 앱 배포: [앱별 문서](../../../README.md#앱별-배포와-상세-작업)
- namespace 감시·배치 보존: [운영 기준](operations.md)
- 실제 제공 인증서 확인·갱신: [인증서 적용](../certificates/apply.md)

## 대상 변경 없는 갱신

기존 공용 진입점의 namespace 감시·배치·VIP backend를 유지하며 원본만 갱신합니다. 실행 위치는 CP1의 저장소 루트입니다.

```bash
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

`VIP_BACKENDS`를 생략하면 기존 배치를 다시 계산하지 않고 보존 가능한지만 검사합니다.
**기대 결과:** 검사 통과 후 적용되고 rollout이 완료됩니다. 기존 앱 접속을 다시 확인합니다. 앱·DB·앱 Secret은 재배포하지 않습니다.
