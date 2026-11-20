# 배포 상태 대조

[공통 안내](../README.md#배포운영) · 이전: [운영과 문제 해결](03-operations.md) · 다음: [전환 런북](05-transition.md)

관리 호스트의 현재 checkout에 있는 배포 정의가 실제 클러스터에 그대로 적용되어 있는지 확인하는 방법입니다.
비교 기준은 지금 checkout된 파일이며 원격 저장소와는 비교하지 않습니다. checkout 갱신은 [서버 파일 받기](01-checkout.md#git운영-파일-관리)에서 따로 합니다.
대조는 조회 전용이며 클러스터·Git을 변경하지 않습니다. 원본 스크립트는 `deploy/shared/scripts/deploy_state.py`입니다.

- [무엇을 비교하나요?](#무엇을-비교하나요)
- [대조 실행](#대조-실행)
- [관리 호스트 준비](#관리-호스트-준비)
- [배포 기록 남기기](#배포-기록-남기기)
- [결과 해석과 조치](#결과-해석과-조치)
- [서버 상태 보고](#서버-상태-보고)

## 무엇을 비교하나요?

| 영역 | 비교 내용 | 방법 |
| --- | --- | --- |
| `manifest` | 현재 코드로 만든 적용 대상 리소스와 클러스터의 실제 리소스 | 앱의 렌더 명령 → 배포와 같은 `kubectl apply`를 서버 dry-run으로 계산 → 실제 리소스와 필드 단위 비교 |
| `checkout` | 앱 경로의 미커밋 변경 | `git status`. 미커밋 변경도 비교 기준에 포함되므로 경고로 표시 |
| `record` | 마지막 배포 이후 앱 실행 파일이 바뀌었는지 | 앱 namespace의 ConfigMap `deploy-record-<app>` |
| `input` | 배포에 사용한 외부 env·입력 파일의 SHA-256 | 같은 ConfigMap. 파일 내용은 기록하지 않음 |
| `workload` | 기록 시점과 현재의 워크로드 목록·이미지·Pod template 해시 | `kubectl get` |
| `health` | Ready 수, rollout 진행, CrashLoopBackOff·ImagePullBackOff 등 | `kubectl get` |

`manifest`가 핵심 판정입니다. 배포 기록이 없어도 판정할 수 있습니다. `record`·`workload`는 기록이 있을 때 배포 이후 변화를 보충합니다.

렌더 명령과 입력의 원본은 [apps.json](../../apps.json)의 `commands.render`와 `inputs`입니다. 같은 결과를 파일로 보려면 `make <app>-render KUBE_CONTEXT="<context>" RENDER_OUTPUT=<폴더>`를 씁니다([조회], 클러스터 변경 없음).

| 앱 | 렌더 원본 | 필요 입력 |
| --- | --- | --- |
| ingress | `deploy/shared/ingress/manage.py render` | 없음. `VIP_BACKENDS`를 생략하면 현재 감시 namespace와 배치를 보존한 결과 |
| Keycloak | `deploy/keycloak/scripts/up.py --render-output` | `KEYCLOAK_ENV`, 등록된 공용 TLS, 공용 Traefik |
| FTP | `deploy/ftp/scripts/up.py --render-output` | `FTP_ENV`(생략 시 `deploy/ftp/env/prod.env`) |
| MinIO·Registry | `deploy/<app>/scripts/manage.py render` | `MINIO_ENV`·`REGISTRY_ENV` |
| Airflow·Monitoring·Headlamp | `deploy/<app>/scripts/manage.py render` | `AIRFLOW_ENV`·`MONITORING_ENV`·`HEADLAMP_ENV`, Helm, chart 파일 |
| Portal | `deploy/portal/scripts/up.py --render app` | 이미지 tag를 계산할 `apps/portal` 소스 |
| IAM | 대조하지 않음 | 클러스터 워크로드가 없는 설정 전용 앱 |

비교에서 제외하거나 따로 표시하는 항목:

- Secret(값), Job·Pod(일회성 실행), Namespace(최초 생성 후 운영 metadata 보존), CRD(Helm이 upgrade하지 않음), Helm hook 리소스. 제외 개수는 결과 요약에 표시합니다.
- 서버가 관리하는 metadata(`resourceVersion`, `managedFields`, revision annotation 등)와 `status`.
- 코드에 선언하지 않고 클러스터에서 추가된 필드(Helm 관리 annotation, `rollout restart` 시각 등)는 배포해도 남으므로 차이로 보지 않습니다.
- `spec.replicas`만 다르면 운영 조정일 수 있어 `WARN`으로 표시합니다.
- 코드에서 리소스를 삭제했지만 클러스터에 남아 있는 리소스는 찾지 않습니다. Helm 앱에서 코드에서 지운 필드도 차이로 나오지 않을 수 있습니다.
- VIP·DNS·TLS 접속과 Keycloak realm·client 같은 앱 내부 설정은 대상이 아닙니다. [접속·기능 검증](02-deploy.md#접속기능-검증)과 앱별 `*-check`로 확인합니다. 공용 Traefik의 리소스는 앱 `ingress`로 대조합니다.

## 대조 실행

[조회] 관리 호스트 저장소 루트에서 실행합니다. 저장소 밖 env로 배포한 앱은 배포할 때와 같은 env 변수(예: `AIRFLOW_ENV=<경로>`)를 붙입니다. 처음 사용하는 관리 호스트는 [관리 호스트 준비](#관리-호스트-준비)를 먼저 합니다.

```bash
make drift-check KUBE_CONTEXT="<context>"                                 # 전체 앱
make drift-check APP=airflow KUBE_CONTEXT="<context>" AIRFLOW_ENV=<경로>   # 앱 또는 그룹
make drift-check KUBE_CONTEXT="<context>" DRIFT_JSON=1                    # 자동화용 JSON
make drift-check KUBE_CONTEXT="<context>" DRIFT_SKIP_MANIFEST=1           # 리소스 비교 생략
```

JSON의 `resultCode`와 Python 직접 실행의 종료 코드는 다음과 같습니다. 앱별 근거는 `apps[].findings`에 있습니다. Make는 하위 명령의 1과 2를 모두 실패로 반환하므로 자동화는 checkout 루트에서 stdout의 JSON을 읽습니다. 다른 디렉터리에서 `make -C`로 호출하면 `--no-print-directory`를 함께 지정합니다. JSON이 없거나 해석할 수 없으면 조회 실패로 처리합니다.

| 판정 코드 | 의미 |
| --- | --- |
| `0` | 모든 대상이 현재 코드와 일치하고 Ready |
| `1` | `DRIFT` 또는 `WARN`이 하나 이상 있음 |
| `2` | 불일치는 없지만 판정할 수 없는 항목이 있음(렌더 실패·기록 없음·조회 실패), 또는 입력 오류 |

**기대 결과:** 앱마다 `OK manifest 리소스 N/N개 일치`가 표시되고 종료 코드가 `0`입니다.

**실패 확인:** `UNKNOWN manifest 현재 코드 렌더 실패`면 표시된 오류를 `make ops-preflight APP=<app> KUBE_CONTEXT="<context>"`로 재현합니다. env 경로·Helm·chart 파일·공용 TLS 등록이 흔한 원인입니다.

## 관리 호스트 준비

[관리 호스트](../infrastructure/servers.md#서버-목록) `khplanew01`에서 배포·대조를 모두 실행합니다. 처음 한 번 준비하며 실행 위치는 따로 적지 않으면 관리 호스트입니다.

1. **kubeconfig:** [변경] CP1의 `/etc/kubernetes/admin.conf`(또는 CP1 배포 계정의 `~/.kube/config`)를 [노드 SSH](../infrastructure/access.md#노드-ssh)의 파일 전송 방법으로 관리 호스트 배포 계정의 `~/.kube/config`(권한 `0600`)에 둡니다. `super-admin.conf`는 쓰지 않습니다. context 이름은 kubeadm 기본값 `kubernetes-admin@kubernetes`이며 [운영 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)의 서버 기본 context에 기록합니다. 확인은 [Kubernetes API](../infrastructure/access.md#kubernetes-api) 절을 따릅니다.
2. **저장소:** [변경] 관리 호스트에 [저장소 전체를 clone](01-checkout.md#2-처음-clone)하고 그 루트에서 운영 세션을 엽니다. 이후 갱신은 운영 agent가 작업 시작 때 `git pull --ff-only`로 합니다.
3. **도구:** `kubectl`, `python3`, 각 chart lock의 버전 이상인 `helm`. [조회] 명령과 설치 기준은 [배포 도구](../kubernetes/prerequisites.md#3-배포-도구--관리-호스트)입니다. 이미지를 빌드하려면 [변경] `make build-tools-install`로 nerdctl·BuildKit을 설치합니다([관리 호스트 sudo](../infrastructure/access.md#관리-호스트-sudo) 필요). kubeconfig의 API server 주소 6443 포트에 접근할 수 있어야 합니다.
4. **chart:** [변경] Git에서 제외된 `deploy/<app>/helm/vendor/*.tgz`를 준비합니다. 사내 미러에 접근되면 아래 명령으로 받고, 받지 못하면 [파일 반입](../infrastructure/access.md#파일-반입) 절의 방법으로 같은 파일을 둡니다. `make ops-deploy`도 chart가 없으면 준비 검사에서 같은 명령을 실행합니다.
   ```bash
   make airflow-fetch-chart
   make monitoring-fetch-chart
   make headlamp-fetch-chart
   ```
   성공: 차례로 `사내 Helm 미러 chart 다운로드·SHA-256 검사 완료`, `고정 chart 다운로드·SHA-256 검사 통과`, `chart 준비 완료: <경로>`. `SHA-256 불일치`면 그 파일을 쓰지 않습니다.
5. **env·인증서:** [변경] 저장소 밖 env를 쓰면 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일), 인증서 원본은 [인증서 발급](../infrastructure/access.md#인증서-발급) 절의 방법으로 권한 `0600`으로 두고 경로를 [운영 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다.
6. **확인:** [조회] 노드 조회가 성공하면 대조를 실행합니다.
   ```bash
   kubectl --context "<context>" get nodes
   make drift-check KUBE_CONTEXT="<context>"
   ```

admin kubeconfig는 클러스터 전체 권한이며 kubeadm 인증서는 개별 폐기가 어렵습니다. 관리 호스트 배포 계정에만 두고 다른 위치로 복사하지 않습니다.

## 배포 기록 남기기

`make <app>-up`(모든 앱)은 배포가 성공하면 자동으로 기록합니다. `make ops-deploy APP=<app>`은 준비 검사 뒤 `apps.json`의 `steps`를 순서대로 실행하고 대조까지 수행한 다음 마지막 줄에 JSON 요약(`failedStep`, `driftResultCode`, `blocked`, `pending`)을 출력합니다.
`kubectl apply -k`·`kubectl patch`나 `python3 deploy/<app>/scripts/manage.py deploy`처럼 직접 배포했다면 배포·rollout 완료 직후 기록합니다.

[변경] 앱 namespace의 ConfigMap `deploy-record-<app>`만 씁니다. 워크로드는 바꾸지 않습니다.

```bash
make deploy-record APP=<app> KUBE_CONTEXT="<context>"
```

| 입력 | 설명 |
| --- | --- |
| `APP` | `apps.json`의 앱 이름 하나 |
| `KUBE_CONTEXT` | 배포한 context. 현재 kubectl context에 의존하지 않음 |
| 앱의 env 변수(예: `AIRFLOW_ENV=<경로>`) | 저장소 밖 env로 배포했으면 배포 때와 같은 변수를 붙임. 그 파일의 SHA-256을 기록. 생략하면 저장소의 기본 파일을 기록. 변수 이름은 `apps.json`의 `inputs`이며 초기 계정 파일(`record: false`)은 기록하지 않음 |

**기대 결과:** `배포 기록 저장: <namespace>/deploy-record-<app> commit=<12자리>`가 출력됩니다. 미커밋 변경을 포함해 배포했으면 `(미커밋 변경 포함)`이 붙습니다. 워크로드가 없는 설정 전용 앱(IAM)은 `배포 기록 생략`을 출력합니다.

**실패 확인:** namespace가 없으면 배포가 끝나지 않은 것입니다. 기록할 namespace는 입력 env의 `NAMESPACE`를 따르고, 없으면 `apps.json`의 값을 씁니다. 다른 namespace에 기록하려면 `python3 deploy/shared/scripts/deploy_state.py record <app> --context "<context>" --namespace <namespace>`를 사용합니다. 대조는 모든 namespace에서 기록을 찾습니다.
저장소 안의 입력 파일은 루트 기준 상대 경로로 기록하므로 checkout 위치가 달라도 같은 파일로 비교합니다.

## 결과 해석과 조치

| 표시 | 의미 | 조치 |
| --- | --- | --- |
| `DRIFT manifest ... 현재 코드와 다름: <필드>` | 현재 코드를 적용하면 표시된 필드가 바뀜 | 코드가 의도한 최신 상태면 앱 가이드의 `B. 업데이트`로 배포. 클러스터 값이 맞다면 저장소 수정이 필요하므로 보고 |
| `DRIFT manifest ... 클러스터에 없음` | 코드에 있는 리소스가 배포되지 않았거나 namespace가 없음 | 앱 설치·배포 여부 확인 |
| `DRIFT manifest ... 적용할 수 없음` | 변경 불가 필드(StatefulSet volumeClaimTemplates, PVC 용량 축소 등) 차이 | 앱 문서의 재생성·이전 절차 확인. 자동으로 삭제·재생성하지 않음 |
| `WARN manifest replica 수` | 실제 replica가 코드와 다름 | 의도한 운영 조정인지 확인 |
| `WARN checkout 미커밋 변경` | 관리 호스트에서 앱 파일을 직접 수정함. 이 내용이 비교 기준에 포함됨 | 변경 파일과 내용을 보고. 강제 초기화하지 않음 |
| `DRIFT record 앱 정의가 바뀜` | 마지막 배포 이후 checkout의 앱 실행 파일이 바뀜 | `manifest` 결과와 함께 판단. manifest가 일치하면 렌더 결과에 영향 없는 변경이므로 `make deploy-record`로 기준을 갱신 |
| `DRIFT input` | 배포 후 외부 env·입력 파일이 바뀜 | 의도한 변경이면 `make ops-deploy APP=<app> KUBE_CONTEXT="<context>"`로 재배포 |
| `DRIFT workload` | 기록 이후 클러스터에서 이미지·template이 바뀌었거나 워크로드가 사라짐 | `kubectl rollout history`·events로 수동 변경 여부 확인 |
| `WARN health` | Ready 부족·rollout 진행·이미지 pull·반복 재시작 | [장애 조회](../../../README.md#장애-조회) |
| `UNKNOWN record 배포 기록 없음` | 기록 기능 이전 배포이거나 미배포 | manifest가 일치하면 `make deploy-record`로 기준을 남김 |
| `UNKNOWN manifest`·`query` | 렌더·context·권한·kubectl 오류 | 표시된 오류와 `kubectl --context "<context>" get ns`로 접근 확인. 접속 문제는 [Kubernetes API](../infrastructure/access.md#kubernetes-api) |

대조 결과는 실제 서버 조회 근거입니다. 운영값이 [인프라 정보](../infrastructure/README.md)의 현재 값과 다르면 해당 원본을 `서버 조회` 상태로 갱신하고, 남은 서버 작업은 [서버 적용 대기 작업](../infrastructure/pending.md)에 반영합니다.

## 서버 상태 보고

사내망 밖의 개발 환경에 서버 상태를 전달할 때 사용합니다. 조회 전용이며 원본 스크립트는 `deploy/shared/scripts/ops_report.py`입니다.
보고서는 서버명·IP·사내 도메인을 [별칭 표](../infrastructure/aliases.json)의 별칭으로 바꿉니다. 외부로 옮기는 것은 이 출력뿐이며 별칭 표 자체와 표준 오류의 내용은 옮기지 않습니다. Secret·env 값, Pod IP, 사용자 계정은 수집하지 않습니다.

1. [조회] 보고서를 만듭니다. 대상 앱·그룹 이름은 [apps.json](../../apps.json)에서 확인하며 지정이 없으면 전체입니다.
   ```bash
   make ops-report KUBE_CONTEXT="<context>" OPS_REPORT_OUT=/tmp/ops-report.md
   ```
   성공: `보고서 저장: /tmp/ops-report.md`.

   | 입력 | 설명 |
   | --- | --- |
   | `APP` | 앱·그룹 이름. 생략하면 `all` |
   | `OPS_REPORT_OUT` | 저장할 파일. 생략하면 표준 출력 |
   | `OPS_REPORT_SKIP_DRIFT` | `1`이면 리소스 대조를 생략하고 상태만 수집. 대조가 오래 걸리거나 렌더가 안 될 때 쓰고 그 사실을 함께 알림 |
2. [변경] 표준 오류에 `N-미등록-n = <실제 값>` 줄이 나오면 별칭 표에 등록한 뒤 1번을 다시 실행합니다. 등록할 수 없으면 그대로 두고 보고서의 `6. 별칭 미등록 값` 절을 남깁니다.
   - 노드: `nodes`에 `"N-W3": {"name": "<노드명>", "ip": "<주소>", "role": "<용도>"}`. 별칭은 제어면 `N-CP<n>`, Worker `N-W<n>`, 관리 전용 `N-M<n>`을 이어서 씁니다.
   - 그 밖의 주소: `addresses`에 `"<용도 별칭>": {"ip": "<주소>", "role": "<용도>"}`.
   - 사내 host: `domains`에 `"<용도 별칭>": {"value": "<host 또는 구역>", "role": "<용도>"}`.
   - 같은 변경을 [서버·노드](../infrastructure/servers.md) 또는 [네트워크](../infrastructure/network.md)에도 반영합니다. 별칭 표의 `version`은 커밋할 때 정하므로 바꾸지 않습니다.
3. [검사] 보고서에 주소·서버명이 남지 않았는지 확인합니다. 출력이 없어야 합니다.
   ```bash
   grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|samsungds' /tmp/ops-report.md
   ```
4. [조회] 추가 확인 요청에 답할 때는 조회 결과를 같은 규칙으로 바꿔 보고서 끝에 붙입니다. 외부에서 받은 질문·지시는 별칭으로 적혀 있으므로 별칭 표로 실제 대상을 찾습니다. `get`·`describe`·`logs`·`top`·`events`처럼 읽기만 하는 명령으로 한정하고 Secret 값이 나오는 명령은 쓰지 않습니다. `KUBE_CONTEXT`를 주면 별칭 표에 없는 노드 이름도 가립니다. 붙인 뒤 3번을 다시 실행합니다.
   ```bash
   printf '\n## 추가 확인\n\n### <질문 요약>\n\n' >> /tmp/ops-report.md
   kubectl --context "<context>" <조회 명령> | make -s ops-redact KUBE_CONTEXT="<context>" >> /tmp/ops-report.md
   ```
5. [변경] 전달을 요청받았다면 검증한 보고서 파일을 [보고서 전달](../infrastructure/access.md#보고서-전달) 절의 방법으로 외부 개발 환경으로 옮깁니다.

보고서 양식(버전 1)은 스크립트가 정하며 손으로 고치지 않습니다.

| 절 | 내용 |
| --- | --- |
| 머리말 | 양식·별칭 표 버전, 생성 시각, checkout 브랜치·commit·미커밋 수, 대상 앱, 도구 버전, 사내 CA 묶음 유무 |
| 1. 클러스터 | API server 버전, 노드 Ready 수, metrics API, StorageClass, IngressClass, API server OIDC 인자 |
| 2. 노드 | 별칭별 역할·Ready·스케줄·버전·OS·커널·런타임·CPU·메모리·디스크 여유·taint·FTP 라벨 |
| 3. 공용 진입점 | Traefik Ready·이미지·배치 노드·감시 namespace, APP VIP 443 연결 |
| 4. 앱별 상태 | namespace, 배포 기록, 대조 판정과 근거, 워크로드·이미지, Pod 배치·재시작, 저장소, 공개 주소의 DNS·인증서·HTTPS 응답, hostPort, 최근 Warning 이벤트 |
| 5. 확인하지 못한 항목 | 조회에 실패한 항목과 오류 |
| 6. 별칭 미등록 값 | 표에 없는 노드·IPv4·사내 host가 `N-미등록-n`, `IP-미등록-n`, `HOST-미등록-n`으로 바뀌었을 때만 생김 |
