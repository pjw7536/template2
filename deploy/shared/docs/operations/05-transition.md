# 전환 런북: 배포된 서버에 새 배포 구조 적용

[공통 안내](../README.md) · 이전: [배포 상태 대조](04-drift.md) · [배포 가이드](../../../README.md)

이미 앱이 배포된 서버가 새 checkout을 받은 뒤 **한 번** 수행하는 순서입니다. 아직 아무 앱도 배포하지 않은 서버는 이 문서가 필요 없고 [앱 설치 순서](../../../README.md#앱-설치-순서)대로 설치합니다.
명령은 관리 호스트의 저장소 루트에서 실행합니다. 단계 표시와 공통 규칙은 [배포 가이드](../../../README.md#문서-읽는-법)를 따릅니다.

이 문서는 임시 문서입니다. 아래 `적용 여부 확인`이 모든 서버에서 `적용됨`이면 항목을 지웁니다.

## 무엇이 바뀌었나요?

| 바뀐 것 | 서버에 미치는 영향 | 처리하는 절 |
| --- | --- | --- |
| 공용 Traefik이 Keycloak 배포에서 분리돼 앱 `ingress`가 됨 | 클러스터 리소스는 그대로. `ingress`의 배포 기록이 없음 | [1. 공용 Traefik 인수](#1-공용-traefik-인수) |
| 앱마다 배포 정의·도구가 바뀌어 배포 기록의 내용 id가 달라짐 | 대조가 `마지막 배포 이후 앱 정의가 바뀜`을 보고 | [2. 배포된 앱의 기록 갱신](#2-배포된-앱의-기록-갱신) |
| Portal API env의 `DJANGO_ALLOWED_HOSTS`·`AIRFLOW_PASSWORD` 기본값 수정 | 저장소 밖 env를 쓰면 같은 수정을 직접 반영해야 함 | [3. Portal env 값 반영](#3-portal-env-값-반영) |
| Airflow 대조가 배포와 같은 설정으로 렌더 | 정상 배포인데 `driftResultCode` 1이던 문제가 사라짐 | [2. 배포된 앱의 기록 갱신](#2-배포된-앱의-기록-갱신) |
| 명령 인자 변경 | 아래 [바뀐 명령](#바뀐-명령) 표 | — |
| 클러스터 밖 작업의 접근 방법을 [접근 경로](../infrastructure/access.md) 한 곳에 기록 | 처음 쓰는 접근 방법을 그 표에 적음 | [4. 접근 경로 기록](#4-접근-경로-기록) |

타깃 이름(`make <app>-check`·`-up`·`-smoke`, `ops-deploy`, `drift-check`)과 env 파일 경로, 배포 기록의 형식은 그대로입니다.

### 바뀐 명령

| 이전 | 지금 |
| --- | --- |
| `make ops-preflight APP=<app> PROFILE=prod KUBE_CONTEXT=…` | `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`. 출력은 `[통과]`·`[자동 준비]`·`[배포 차단]`·`[안내]`와 마지막 줄 `준비 검사 결과: …` |
| `make deploy-record APP=<app> … RECORD_INPUTS=<파일>` | `make deploy-record APP=<app> KUBE_CONTEXT="<context>"`. 저장소 밖 env는 배포와 같은 변수(예: `AIRFLOW_ENV=<경로>`)로 지정 |
| `make keycloak-up … VIP_BACKENDS=<목록>` | `make ops-deploy APP=ingress KUBE_CONTEXT="<context>" VIP_BACKENDS=<목록>`([승인]) |
| `make keycloak-up`이 Traefik도 적용 | `make ops-deploy APP=ingress KUBE_CONTEXT="<context>"`가 Traefik을 적용. Keycloak 배포는 Traefik이 있는지만 확인 |
| `make minio-render`, `make registry-render` | `make <app>-render KUBE_CONTEXT="<context>" RENDER_OUTPUT=<폴더>` |
| DNS 등록 전 `make <app>-smoke … SMOKE_CONNECT=<APP VIP 주소>` | `make <app>-smoke KUBE_CONTEXT="<context>"`가 APP VIP로 자동 재확인하고 `DNS 미등록`으로 표시 |
| `APP`을 빼면 keycloak 대상 | `APP`을 빼면 실행되지 않음(`drift-check`·`ops-report`만 전체 대상) |
| `kubectl delete job minio-init` 뒤 재배포 | `make ops-deploy APP=minio KUBE_CONTEXT="<context>"`가 버킷 초기화를 다시 실행 |

## 적용 여부 확인

[조회] 배포 기록이 있는 앱을 조회합니다.

```bash
kubectl --context "<context>" get configmaps -A -l deploy-record -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name
```

| 결과 | 판단 |
| --- | --- |
| 목록이 비어 있고 `kubectl --context "<context>" -n etch-sso get deployment traefik --ignore-not-found`도 비어 있음 | 배포된 앱이 없습니다. 이 문서를 건너뜁니다 |
| `deploy-record-ingress`가 있음 | `적용됨`. 이 문서를 건너뜁니다 |
| 그 밖(Traefik이나 다른 앱의 기록은 있는데 `deploy-record-ingress`가 없음) | 미적용. 아래 0~5를 순서대로 수행합니다 |

## 0. 시작 전 검사

1. [검사] 새 checkout의 배포 정의를 클러스터 없이 검사합니다.
   ```bash
   make server-check APP=all
   ```
   성공: 앱마다 `서버 원본 검사 통과: <app>`. 실패하면 저장소 문제이므로 멈추고 실패한 앱과 오류 마지막 줄을 보고합니다. 클러스터는 아직 바뀌지 않았습니다.
2. [조회] 어떤 앱이 배포돼 있는지 확인하고 기록해 둡니다.
   ```bash
   make drift-check KUBE_CONTEXT="<context>" DRIFT_JSON=1 DRIFT_SKIP_MANIFEST=1
   ```
   `apps[]`에서 `findings`에 `대상 워크로드 없음`이 **없는** 앱이 배포된 앱입니다. 이 시점의 `resultCode` 1·2는 정상입니다(기록이 이전 정의를 가리킴).
3. [조회] 공용 Traefik의 현재 감시 namespace와 배치를 적어 둡니다. 1단계 뒤에 같은지 비교합니다.
   ```bash
   kubectl --context "<context>" -n etch-sso get deployment traefik -o jsonpath='{.spec.replicas}{"\n"}{.spec.template.spec.containers[0].args}{"\n"}{.metadata.annotations.deploy\.tailwind\.local/vip-backends}{"\n"}'
   ```

저장소 밖 env로 배포한 앱은 이 문서의 모든 `make` 명령에 같은 env 변수(예: `AIRFLOW_ENV=<경로>`)를 붙입니다. 변수 이름은 각 앱 가이드의 `입력` 표에 있습니다.

## 1. 공용 Traefik 인수

Traefik이 이미 있으면 같은 리소스를 `ingress` 앱의 이름으로 다시 적용하고 배포 기록을 만듭니다. 감시 namespace와 VIP 배치는 보존됩니다.

1. [검사] 변경 없이 검사합니다.
   ```bash
   make ingress-check KUBE_CONTEXT="<context>"
   ```
   성공: `공용 Ingress 원본·배치 검사 통과. 클러스터를 변경하지 않았습니다.`
2. [변경] 적용하고 기록합니다. Pod template이 같으면 Traefik은 다시 시작되지 않습니다.
   ```bash
   make ops-deploy APP=ingress KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.
3. [조회] 0-3의 명령을 다시 실행해 replica 수, `--providers.kubernetesingress.namespaces=` 값, VIP 기록이 전과 같은지 확인합니다. 다르면 멈추고 전후 값을 보고합니다. 손으로 고치지 않습니다.
4. [조회] 공개 주소가 그대로 응답하는지 확인합니다. 배포된 앱마다 실행합니다.
   ```bash
   make <app>-smoke KUBE_CONTEXT="<context>"
   ```

## 2. 배포된 앱의 기록 갱신

0-2에서 배포된 것으로 확인한 앱마다 [앱 설치 순서](../../../README.md#앱-설치-순서) 표의 순서로 수행합니다(`ingress`는 1단계에서 끝났습니다).

1. [조회] 리소스까지 대조합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>"
   ```
2. 결과에 따라 하나를 수행합니다.

   | `manifest` 줄 | 뜻 | 할 일 |
   | --- | --- | --- |
   | `리소스 n/n개 일치`이고 `DRIFT manifest` 줄이 없음 | 클러스터는 새 정의와 같고 기록만 이전 내용을 가리킴 | [변경] 기록을 갱신합니다. Pod는 다시 시작되지 않습니다 |
   | `DRIFT manifest …` 줄이 있음 | 새 정의가 클러스터와 다름 | 그 앱 가이드의 `B. 업데이트`에서 변경 종류에 맞는 행을 수행합니다. [승인]으로 표시된 행은 승인을 거칩니다 |
   | `UNKNOWN manifest 현재 코드 렌더 실패` | 입력이나 chart가 없음 | `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`로 원인을 확인합니다 |

   기록만 갱신하는 명령입니다.
   ```bash
   make deploy-record APP=<app> KUBE_CONTEXT="<context>"
   ```
   성공: `배포 기록 저장: <namespace>/deploy-record-<app> commit=…`.
3. [조회] 다시 대조해 `resultCode` 0을 확인합니다.
   ```bash
   make drift-check APP=<app> KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```

Keycloak은 Traefik 리소스가 정의에서 빠졌을 뿐 Keycloak 자체 리소스는 같으므로 보통 기록 갱신만 필요합니다.

## 3. Portal env 값 반영

Portal이 배포돼 있을 때만 수행합니다.

1. [검사] Portal API env에 Airflow가 호출하는 클러스터 내부 host가 허용돼 있는지 확인합니다. 저장소 밖 env를 쓰면 그 경로를, 아니면 `deploy/portal/env/prod/api.env`를 넣습니다.
   ```bash
   grep -c '^DJANGO_ALLOWED_HOSTS=.*api\.tailwind-internal\.svc\.cluster\.local' "<Portal API env 경로>"
   ```
   `1`이면 반영돼 있습니다. `0`이면 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일)의 방법으로 그 파일의 `DJANGO_ALLOWED_HOSTS` 값 끝에 `,api.tailwind-internal.svc.cluster.local`을 더합니다.
2. [검사] Portal이 쓰는 Airflow 계정 비밀번호가 Airflow 관리자 비밀번호와 같은지 값 없이 비교합니다.
   ```bash
   bash -c '[ "$(grep "^AIRFLOW_PASSWORD=" "$1" | cut -d= -f2-)" = "$(grep "^AIRFLOW_ADMIN_PASSWORD=" "$2" | cut -d= -f2-)" ] && echo 일치 || echo 불일치' _ "<Portal API env 경로>" "<Airflow env 경로>"
   ```
   `불일치`면 Portal API env의 `AIRFLOW_PASSWORD`를 Airflow env의 `AIRFLOW_ADMIN_PASSWORD` 값으로 맞춥니다. Airflow 쪽 값은 바꾸지 않습니다.
3. [변경] 1·2에서 값을 고쳤거나 저장소 기본 env를 쓰고 있으면 Portal에 반영합니다. API 이미지가 같으면 migration은 실행되지 않고 Pod만 다시 시작됩니다.
   ```bash
   make ops-deploy APP=portal KUBE_CONTEXT="<context>"
   ```
   성공: `{"app":`으로 시작하는 JSON 줄의 `"failedStep": null`, `"driftResultCode": 0`.

## 4. 접근 경로 기록

[변경] [접근 경로](../infrastructure/access.md)에서 `접근 방법`이 `미확인`인 절 가운데 이미 사용해 본 방법(노드 SSH, DNS 신청, 인증서 파일 위치 등)을 `찾는 방법`의 [조회]로 확인해 채웁니다. 비밀값은 쓰지 않고 위치만 적습니다. 아직 써 보지 않은 절은 `미확인`으로 둡니다.

## 5. 완료 확인과 기록

1. [조회] 전체를 대조합니다.
   ```bash
   make drift-check KUBE_CONTEXT="<context>" DRIFT_JSON=1
   ```
   배포된 앱이 모두 `findings`에 `drift`·`warn`이 없으면 끝입니다. 아직 배포하지 않은 앱의 `배포 기록 없음`·`대상 워크로드 없음`은 남아도 됩니다.
2. [조회] `적용 여부 확인`의 명령에 `deploy-record-ingress`가 나오는지 확인합니다.
3. [변경] [대기 작업](../infrastructure/pending.md)에서 확인된 행을 정리하고, 남은 일(막힌 단계와 필요한 것)을 행으로 남깁니다.

## 실패했을 때

- 0단계에서 실패하면 클러스터는 바뀌지 않았습니다. 실패한 검사와 오류 마지막 줄을 보고합니다.
- 1단계의 `ops-deploy`가 실패하면 `failedStep`과 [ingress 가이드](../../ingress/README.md#문제-해결과-멈춤-조건)의 표를 봅니다. Traefik을 지우거나 `kubectl apply -k`로 다시 만들지 않습니다.
- 2·3단계에서 한 앱이 실패하면 그 앱만 멈추고 다음 앱을 계속합니다. 앱 가이드의 `문제 해결과 멈춤 조건`을 따릅니다.
- checkout을 이전 commit으로 되돌리지 않습니다. 저장소 수정이 필요하면 원인과 필요한 수정을 보고합니다.
