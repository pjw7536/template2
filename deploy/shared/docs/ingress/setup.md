# Traefik 셋업

[Ingress 안내](../README.md#https인증서) · [CP1~3 셋업](../kubernetes/control-plane.md) · [Worker 추가](../kubernetes/worker.md)

목표는 **앱들이 함께 사용하는 HTTPS 진입점**을 준비하는 것입니다.
Traefik을 배치할 Ready Worker가 최소 한 대 있어야 합니다.
새 클러스터에서 Worker가 없다면 [Worker 추가](../kubernetes/worker.md)를 먼저 진행합니다.
기존 배치를 그대로 갱신할 때는 [대상 변경 없는 갱신](#대상-변경-없는-갱신)을 사용합니다.

```text
브라우저 → APP VIP:443 → Traefik이 있는 Worker:443 → 앱 Service → 앱 Pod
```

APP VIP는 외부 요청용입니다. Kubernetes 관리용 API VIP와 구분합니다.
앱 Pod는 Traefik과 다른 Worker에 있어도 클러스터 네트워크로 연결됩니다.

이 명령은 `deploy/shared`와 루트 Makefile만 사용하며 앱 env·소스·local 파일을 읽지 않습니다.
`ingress-check`는 공통 원본·노드·선언된 포트 충돌을 검사하고 클러스터를 변경하지 않습니다.
`ingress-up`은 공용 namespace·리소스를 준비하며 Keycloak·DB·다른 앱을 재배포하지 않습니다.
OS 프로세스의 80/443 점유와 실제 VIP·HTTPS 응답은 별도로 확인합니다.


APP VIP는 외부 요청을 Traefik Worker로 전달합니다. 앱·DB의 실행 Worker와 구분하며 backend 추가가 앱·DB 복제를 뜻하지 않습니다.
LB가 TCP 443을 Worker에 전달하고 TLS는 Traefik에서 종료하는 구성을 기준으로 합니다. TLS offloading·PROXY protocol을 사용한다면 LB와 Traefik 입력을 함께 확인합니다.

## 1. 배포 대상·포트 확인 — CP1·선택한 Worker

CP1 배포 계정에 Git·Bash·Make·Python 3.10+·kubectl·OpenSSL과 필요한 저장소 파일을 준비합니다.
[선택 checkout](../operations/01-checkout.md#선택-checkout)을 사용하며 아래 Make 명령은 저장소 루트에서 실행합니다.

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

`VIP_BACKENDS`에는 LB에 연결할 **기존 Worker와 새 Worker IP 전체**를 넣습니다.
기존 Backend를 빼고 적용하지 않습니다. 이미 배치된 Traefik을 그대로 갱신할 때는
`VIP_BACKENDS` 인자를 생략하면 기존 배치를 보존합니다.

선택한 Worker에서는 `sudo ss -lntp '( sport = :80 or sport = :443 )'`로 OS 프로세스의 포트 점유를 확인합니다.
기존 프로세스는 담당자와 조정합니다. Kubernetes hostPort 충돌은 위 검사에서도 확인합니다.
ss 출력만으로 Traefik의 hostPort 사용 여부를 판단하지 않습니다.

## 2. 사용할 도메인의 TLS 인증서 등록 — CP1

공개 도메인의 fullchain PEM과 짝이 맞는 개인키를 준비하고 실행합니다.
필요한 도메인마다 반복합니다. 기존 인증서 파일·Secret에서 가져오는 방법은 [인증서 참고](../certificates/apply.md#2-2-kubernetes-tls-secret에-등록-또는-갱신)를 사용합니다.

```bash
read -r -p '공개 도메인: ' TLS_HOST
read -r -p 'fullchain PEM 절대 경로: ' TLS_CERT_FILE
read -r -p 'PEM 개인키 절대 경로: ' TLS_KEY_FILE
make ingress-tls-up KUBE_CONTEXT="$KUBE_CONTEXT" TLS_HOST="$TLS_HOST" \
  TLS_CERT_FILE="$TLS_CERT_FILE" TLS_KEY_FILE="$TLS_KEY_FILE"
```

인증서는 공용 `etch-sso/traefik-tls`에 등록됩니다.
도구가 도메인·만료·키 일치를 검사하며 다른 도메인의 인증서는 유지합니다.

## 3. Traefik 설치·갱신 — CP1

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
kubectl --context "$KUBE_CONTEXT" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

대상 Worker마다 Traefik이 하나씩 Ready여야 합니다. 사용 namespace는 `etch-sso`입니다.
이 명령은 공용 진입점만 준비합니다. 사용할 앱은 [앱별 문서](../../../README.md#앱별-배포와-상세-작업)로 배포합니다.

## 4. 앱 경로·VIP 확인 — CP1·인프라 담당자

처음 설치했다면 앱 Ingress를 연결한 뒤 실제 앱의 정상 경로를 사용합니다.
기존 서비스가 있으면 그 경로로 바로 검사할 수 있습니다.

```bash
read -r -p '검사할 공개 도메인: ' CHECK_HOST
read -r -p '정상 응답을 확인할 앱 경로(/로 시작): ' CHECK_PATH
read -r -p '직접 검사할 Worker IP: ' CHECK_WORKER_IP
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$CHECK_HOST:443:$CHECK_WORKER_IP" "https://$CHECK_HOST$CHECK_PATH"
read -r -p 'APP VIP: ' APP_VIP
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --resolve "$CHECK_HOST:443:$APP_VIP" "https://$CHECK_HOST$CHECK_PATH"
```

모든 대상 Worker의 직접 HTTPS 검사가 성공한 뒤, 인프라 담당자가 새 LB Backend를 활성화하고
VIP 요청을 검사합니다. 사내 CA가 신뢰 저장소에 없으면 curl에 `--cacert`로 지정합니다.
앱이 아직 없는 `/`의 404만으로 Traefik 장애라고 판단하지 않습니다.

**완료:** 대상 Traefik Ready → 각 Worker의 실제 앱 HTTPS 정상 → LB Backend UP → VIP·DNS로 앱 접속 정상.

문제 해결·namespace 감시는 [공용 Ingress 상세](operations.md), 기존 TLS 이전은 [인증서 적용](../certificates/apply.md#기존-설치에서-이전),
백업·복구와 ingress Worker 확장은 [Traefik·VIP 확장](expand.md)을 참고합니다.

## 대상 변경 없는 갱신

기존 공용 진입점의 namespace 감시·배치·VIP backend를 유지하며 원본만 갱신할 때 사용합니다.
관리 호스트의 저장소 루트에서 실행하며, 새 backend 추가에는 위 최초 설치 절차나 [확장 절차](expand.md)를 사용합니다.

```bash
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT"
```

검사 성공 후 적용하고 rollout·기존 앱 접속을 확인합니다. 앱·DB·앱 Secret은 재배포하지 않습니다.
