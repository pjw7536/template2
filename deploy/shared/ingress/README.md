# 공용 Traefik(ingress) 배포 가이드

[배포 가이드](../../README.md) · [공통 절차](../docs/README.md#https인증서)

여러 앱이 함께 쓰는 HTTPS 진입점(공용 Traefik)을 설치·운영하는 문서입니다. 카탈로그의 앱 이름은 `ingress`입니다. 단계 표시([조회]·[검사]·[변경]·[승인])와 공통 규칙은 [배포 가이드](../../README.md#문서-읽는-법)를 따릅니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| 역할 | APP VIP의 80·443 요청을 받아 TLS를 끝내고 host별로 앱 Service에 전달 |
| namespace | `etch-sso` (Deployment `traefik`, Secret `traefik-tls`, IngressClass `traefik`). Keycloak과 같은 namespace를 씁니다 |
| 실행 Worker | [stack.yaml](stack.yaml)의 `nodeSelector` 노드 한 대가 기본. VIP backend를 지정하면 backend 노드마다 하나씩 |
| 포트 | 각 Traefik 노드의 hostPort 80, 443 |
| 배포 명령 | `make ops-deploy APP=ingress` = 준비 검사 → `ingress-check` → `ingress-up` → `ingress-smoke` → 대조 |
| 완료 기준 | `ops-deploy` 요약의 `failedStep` `null`·`driftResultCode` `0`, `smoke 통과: ingress` |
| 먼저 필요한 것 | Ready Worker. 다른 앱은 필요 없습니다 |

## 구성

- 원본: [stack.yaml](stack.yaml)(ServiceAccount·RBAC·IngressClass·Deployment·Service), [kustomization.yaml](kustomization.yaml)(사내 미러 이미지), `middlewares/`.
- 도구: `manage.py`(검사·렌더·배포, Portal 감시 연결), `routing.py`(감시 namespace·배치 보존, VIP·Worker 후보 검사), `tls.py`(공용 인증서 등록·검사).
- 감시 범위: Traefik은 `--providers.kubernetesingress.namespaces`에 적힌 namespace의 Ingress만 읽습니다. 앱은 자기 배포(`<app>-up`)에서 자기 namespace를 이 목록에 더합니다. `ingress-up`은 현재 목록을 보존합니다.
- 배치: `VIP_BACKENDS`를 주지 않으면 현재 replica·nodeSelector·affinity·VIP 기록을 그대로 둡니다. 보존·검사 규칙은 [운영 기준](../docs/ingress/operations.md)에 있습니다.
- 인증서: `etch-sso/traefik-tls` Secret 한 곳에 host별로 보관하고 Traefik이 SNI로 고릅니다. 앱 namespace에는 TLS Secret을 두지 않습니다.

현재 주소·backend·노드 대응은 [VIP와 backend](../docs/infrastructure/network.md#vip와-backend)에서 관리합니다.

## 사전 준비

완료 여부를 확인하고 미완료면 준비 작업을 수행합니다.

| 준비 작업 | 완료 확인 |
| --- | --- |
| Traefik을 둘 Worker가 `Ready`이고 cordon·차단 taint가 없음 | `kubectl --context "<context>" get nodes` |
| 그 Worker의 80·443을 다른 프로세스가 쓰지 않음(Kubernetes Pod의 hostPort 충돌은 `ingress-check`가 확인) | [노드 명령 실행](../docs/infrastructure/access.md#노드-명령-실행)의 `python3 deploy/shared/scripts/node_exec.py <노드> --context "<context>" --command 'sudo ss -lntp "( sport = :80 or sport = :443 )"'` |
| APP VIP가 Traefik 노드의 80·443으로 전달 | [APP VIP와 LB](../docs/infrastructure/access.md#app-vip와-lb) |

## 입력

env 파일은 없습니다. 선택 입력만 있습니다.

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `VIP_BACKENDS` | Traefik을 배치할 전체 Worker IP 목록(쉼표 구분). 기존 backend를 포함한 전체를 적습니다 | 비우면 현재 배치를 보존. 처음 설치면 `stack.yaml`의 노드 한 대 |

## A. 최초 설치

1. [변경] 배포. namespace `etch-sso`가 없으면 만들고 Traefik을 적용한 뒤 기동을 기다립니다.
   ```bash
   make ops-deploy APP=ingress KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`. 출력에 `공용 Ingress 준비 완료`가 있습니다.
2. [조회] [C. 배포 후 확인](#c-배포-후-확인)

공개 host의 인증서는 각 앱을 배포할 때 준비 검사가 등록합니다. 직접 등록하려면 [공용 TLS 등록](../../README.md#공용-tls-등록)을 씁니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| 이미지·인자 등 저장소 원본 | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`. Traefik Pod가 다시 시작되는 동안 그 노드를 지나는 요청이 잠시 끊깁니다 |
| 인증서 갱신·추가 | [변경] [공용 TLS 등록](../../README.md#공용-tls-등록). 등록 뒤 Traefik이 다시 시작됩니다 |
| VIP backend 추가·변경 | [승인] 진입 경로가 바뀝니다. 대상 IP 전체와 영향을 보여 주고 승인받은 뒤 [backend 확장](../docs/ingress/expand.md) |
| Portal namespace 감시 연결만 복구 | [변경] `make ingress-connect APP=portal KUBE_CONTEXT="<context>"` |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n etch-sso get deployment traefik
kubectl --context "<context>" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
make ingress-smoke KUBE_CONTEXT="<context>"
```

성공: Deployment READY가 replica 수와 같음, Pod `Running`, `smoke 통과: ingress`. smoke의 tcp 줄은 관리 호스트에서 각 Traefik 노드의 443 연결을 확인합니다.

## 문제 해결과 멈춤 조건

Pod·이벤트·로그는 [장애 조회](../../README.md#장애-조회)의 명령에 namespace `etch-sso`를 넣어 조회합니다.

| 증상 | 원인과 조치 |
| --- | --- |
| `ingress-check`가 노드·포트 오류로 실패 | 표시된 노드의 Ready·cordon·taint와 80·443을 쓰는 Pod를 조회. 원인을 없앤 뒤 같은 명령 재실행 |
| `기존 backend`를 뺐다는 오류 | `VIP_BACKENDS`에 현재 backend를 모두 포함해 다시 실행 |
| smoke tcp 줄이 `연결 실패` | Traefik Pod가 `Running`인지 조회. Running이면 관리 호스트에서 그 노드 443까지의 경로를 [방화벽](../docs/infrastructure/access.md#방화벽) 절로 확인 |
| 앱 배포가 `공용 TLS 마운트가 없습니다`로 실패 | [변경] `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`로 원본을 다시 적용 |
| 특정 앱만 404 | 그 앱 namespace가 감시 목록에 없음. 그 앱의 `make <app>-up KUBE_CONTEXT="<context>"`를 다시 실행(Portal은 B의 감시 연결) |

다음이면 멈추고 보고합니다.

- 기록된 VIP backend와 실제 배치가 다르다는 오류. replica·nodeSelector를 손으로 고치지 않습니다.
- `kubectl apply -k deploy/shared/ingress`를 직접 실행해야 할 것처럼 보이는 경우. 감시 namespace와 VIP 배치가 기본값으로 돌아가므로 실행하지 않습니다.
- Traefik Pod가 `Pending`이거나 재시작을 반복하는 경우. 노드·이벤트·로그 끝을 함께 보고합니다.

## 상세 문서

| 문서 | 내용 |
| --- | --- |
| [Traefik 셋업](../docs/ingress/setup.md) | VIP 구성과 backend를 지정한 설치, 포트 확인 |
| [Traefik·VIP 확장](../docs/ingress/expand.md) | 운영 중 backend 추가, 백업과 복구 |
| [운영 기준](../docs/ingress/operations.md) | 배치 보존 규칙, TLS와 도메인 라우팅, namespace 감시 계약 |
| [인증서 준비](../docs/certificates/prepare.md) → [추출](../docs/certificates/extract.md) → [적용](../docs/certificates/apply.md) | 인증서 파일 준비와 등록 뒤 확인 |
