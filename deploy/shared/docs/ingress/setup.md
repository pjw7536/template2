# Traefik 셋업

[가이드 홈](../README.md#https인증서) · [ingress 가이드](../../ingress/README.md) · [Worker 추가](../kubernetes/worker.md) · [운영 기준](operations.md) · [Traefik·VIP 확장](expand.md)

**목적:** 앱들이 함께 사용하는 HTTPS 진입점(공용 Traefik, 카탈로그 앱 `ingress`)의 VIP 구성과, backend Worker를 지정한 설치·검증을 다룹니다.
backend를 지정하지 않는 설치·갱신·확인은 [ingress 가이드](../../ingress/README.md)를 따릅니다.

```text
브라우저 → APP VIP:443 → Traefik이 있는 Worker:443 → 앱 Service → 앱 Pod
```

- APP VIP는 외부 요청용이며 Kubernetes 관리용 API VIP와 구분합니다. 현재 주소·backend는 [네트워크 원본](../infrastructure/network.md#vipdns접속-경로)을 따릅니다.
- LB가 TCP 443을 Worker에 전달하고 Traefik이 TLS를 종료하는 구성을 기준으로 합니다. TLS offloading·PROXY protocol을 쓴다면 LB와 Traefik 입력을 함께 확인합니다.
- 앱 Pod는 Traefik과 다른 Worker에 있어도 클러스터 네트워크로 연결됩니다. backend 추가가 앱·DB 복제를 뜻하지 않습니다.

**어느 문서를 쓰나요?**

| 상황 | 절차 |
| --- | --- |
| 최초 설치, backend 변경 없이 저장소 원본(이미지·인자)으로 갱신 | [ingress 가이드](../../ingress/README.md)의 `A. 최초 설치`·`B. 업데이트` |
| Traefik이 아직 없는 클러스터에 backend Worker를 지정해 설치 | 이 문서 1~5 |
| 운영 중인 Traefik의 backend 추가(백업·복구 포함) | [Traefik·VIP 확장](expand.md) |

**준비물:**

- Traefik을 배치할 Ready Worker. `VIP_BACKENDS`에는 서로 다른 Worker 주소를 두 개 이상 지정합니다. Worker가 없으면 [Worker 추가](../kubernetes/worker.md)를 먼저 진행합니다.
- 관리 호스트 배포 계정의 [배포 도구](../kubernetes/prerequisites.md#3-배포-도구--관리-호스트)와 [관리 호스트 저장소](../operations/01-checkout.md#저장소-clone)
- backend Worker의 주소. [VIP와 backend](../infrastructure/network.md#vip와-backend)의 기록과 1단계 노드 조회의 `INTERNAL-IP`를 대조합니다.

**실행 위치:** 관리 호스트의 저장소 루트. Worker에서 하는 조회는 그 단계에 적습니다. `ingress` 명령은 `deploy/shared`와 루트 Makefile만 사용하며 앱 env·소스·local 파일을 읽지 않습니다.

**자리표시:** `<IP 목록>`은 LB에 연결할 Worker의 InternalIP 전체를 쉼표로 이은 값, `<공개 host>`와 `<경로>`는 이미 배포된 앱의 공개 host와 정상 응답 경로(예: Keycloak realm `etch`는 `/realms/etch/.well-known/openid-configuration`), `<CA PEM 파일>`은 [사내 CA 묶음](../../../README.md#사내-ca-묶음)의 `deploy/shared/certs/sso.etch.samsungds.net/keycloak-ca-bundle.pem`입니다.

## 1. 배포 대상·포트 검사 — 관리 호스트·선택한 Worker

[조회] 노드와 현재 Traefik을 조회합니다.

```bash
kubectl config get-contexts
kubectl --context "<context>" get nodes -o wide
kubectl --context "<context>" -n etch-sso get deployment traefik --ignore-not-found
```

마지막 명령의 출력이 있으면 Traefik이 이미 운영 중입니다. backend를 바꾸는 것은 [승인] 단계이므로 이 문서 대신 [Traefik·VIP 확장](expand.md)을 따릅니다.

[검사] 지정할 배치를 검사합니다. 클러스터를 변경하지 않습니다.

```bash
make ingress-check KUBE_CONTEXT="<context>" VIP_BACKENDS=<IP 목록>
```

- `VIP_BACKENDS`에는 LB에 연결할 **기존 Worker와 새 Worker IP 전체**를 넣습니다. 기존 backend를 빼고 적용하지 않습니다.
- `ingress-check`는 공통 원본·노드 Ready·cordon·taint·선언된 80/443 hostPort 충돌을 검사하며 클러스터를 변경하지 않습니다.

**기대 결과:** `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`

**실패 확인:** 표시된 노드·IP·포트 충돌 또는 기존 backend 누락을 해결한 뒤 다시 검사합니다. 검사 실패 상태로 2단계 이후를 진행하지 않습니다.

[조회] 선택한 각 Worker에서 OS 프로세스의 포트 점유도 확인합니다. 실행 위치는 그 Worker이며, 블록을 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다.

```bash
sudo ss -lntp '( sport = :80 or sport = :443 )'
```

Nginx 등 다른 프로세스가 점유 중이면 그 Worker를 backend에 넣지 않습니다. 프로세스를 종료하지 않고 출력과 함께 보고합니다.
hostPort는 네트워크 규칙으로 구현될 수 있으므로 ss 출력이 비어 있어도 Traefik이 실행 중일 수 있습니다.

## 2. TLS 인증서 등록 — 관리 호스트

공개 host의 인증서는 그 host를 쓰는 앱의 `make ops-deploy`가 준비 검사에서 자동으로 등록합니다. 직접 등록하거나 갱신할 때는 [공용 TLS 등록](../../../README.md#공용-tls-등록)의 `make ingress-tls-up`을 host마다 실행합니다.
파일 준비·추출은 [인증서 원본 준비](../certificates/prepare.md)부터 시작하고, 기존 TLS Secret에서 가져오는 `TLS_SOURCE` 방식과 등록 뒤 확인은 [인증서 적용](../certificates/apply.md#2-공용-tls-secret-등록갱신--관리-호스트)에 있습니다.

인증서는 공용 `etch-sso/traefik-tls`에 등록됩니다. 도구가 도메인·만료·키 일치를 검사하며 다른 도메인의 인증서는 유지합니다.

## 3. Traefik 설치·갱신 — 관리 호스트

[변경] Traefik이 아직 없는 클러스터의 설치입니다. 준비 검사 → `ingress-check` → `ingress-up` → `ingress-smoke` → 대조를 수행합니다.

```bash
make ops-deploy APP=ingress KUBE_CONTEXT="<context>" VIP_BACKENDS=<IP 목록>
```

성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `공용 Ingress 준비 완료`가 있습니다.

[조회] 배치를 확인합니다.

```bash
kubectl --context "<context>" -n etch-sso get pods \
  -l app.kubernetes.io/name=traefik -o wide
```

**기대 결과:** 대상 Worker마다 Traefik이 하나씩 `1/1 Running`입니다.

`ingress-up`은 `etch-sso` namespace와 공용 리소스를 준비하며 Keycloak·DB·다른 앱을 재배포하지 않습니다.
지정한 배치는 Deployment의 `deploy.tailwind.local/vip-backends` annotation에 기록되어, 이후 `VIP_BACKENDS` 없이 실행하는 `make ops-deploy APP=ingress`와 앱 배포가 그대로 보존합니다.

**실패 확인:** 아래 표와 [ingress 가이드의 문제 해결](../../ingress/README.md#문제-해결과-멈춤-조건)을 봅니다.

| 상태 | 먼저 확인할 내용 |
| --- | --- |
| Pending | `kubectl describe pod`의 이벤트 |
| ImagePullBackOff | 해당 노드의 이미지 미러·인증 |
| Ready 실패 | Pod 로그와 CNI 연결 |

## 4. Worker 직접 → APP VIP 검증 — 관리 호스트

처음 설치했다면 앱 Ingress를 연결한 뒤(앱 배포 뒤) 실제 앱의 정상 경로를 사용합니다. 기존 서비스가 있으면 그 경로로 바로 검사합니다.
OS가 사내 CA를 신뢰하면 `--cacert <CA PEM 파일>`을 생략할 수 있습니다. 인증서 검증을 건너뛰는 `-k`는 쓰지 않습니다.

[조회] 각 Traefik 노드의 443 연결을 확인하고, `<Worker IP>`를 바꿔 가며 모든 대상 Worker에 직접 요청합니다.

```bash
make ingress-smoke KUBE_CONTEXT="<context>"
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
  --resolve "<공개 host>:443:<Worker IP>" "https://<공개 host><경로>"
```

성공: `smoke 통과: ingress`와 Worker마다 정상 응답.

[변경] 모든 대상 Worker의 직접 요청이 성공한 뒤 LB에서 새 backend를 활성화하고 Health Check가 UP인지 확인합니다. LB 작업은 [APP VIP와 LB](../infrastructure/access.md#app-vip와-lb) 절의 방법으로 합니다.

[조회] 그다음 APP VIP를 검사합니다. `<APP VIP 주소>`는 [별칭 표](../infrastructure/aliases.json)의 `VIP-APP`입니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 --cacert <CA PEM 파일> \
  --resolve "<공개 host>:443:<APP VIP 주소>" "https://<공개 host><경로>"
```

**실패 확인:** 앱이 아직 없는 `/`의 404만으로 Traefik 장애라고 판단하지 않습니다. 한 번의 VIP 성공만으로 모든 backend가 정상이라고 판단하지 않습니다.

## 5. 완료 기준과 다음 단계

대상 Traefik Ready → 각 Worker의 실제 앱 HTTPS 정상 → LB backend UP → VIP·DNS로 앱 접속 정상.
확인한 backend와 노드 대응은 [VIP와 backend](../infrastructure/network.md#vip와-backend)에 반영합니다.

- 앱 배포: [앱별 문서](../../../README.md#앱-설치-순서)
- namespace 감시·배치 보존: [운영 기준](operations.md)
- 실제 제공 인증서 확인·갱신: [인증서 적용](../certificates/apply.md)

## 대상 변경 없는 갱신

기존 공용 진입점의 namespace 감시·배치·VIP backend를 유지하며 원본만 갱신하는 절차는 [ingress 가이드의 B. 업데이트](../../ingress/README.md#b-업데이트)입니다.
`VIP_BACKENDS`를 생략하면 기존 배치를 다시 계산하지 않고 보존 가능한지만 검사합니다. 앱·DB·앱 Secret은 재배포하지 않습니다.
