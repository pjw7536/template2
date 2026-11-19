# 배포 상태 대조

[공통 안내](../README.md#배포운영) · 이전: [운영과 문제 해결](03-operations.md)

CP1의 현재 checkout에 있는 배포 정의가 실제 클러스터에 그대로 적용되어 있는지 확인하는 방법입니다.
비교 기준은 지금 checkout된 파일이며 원격 저장소와는 비교하지 않습니다. checkout 갱신은 [서버 파일 받기](01-checkout.md#git운영-파일-관리)에서 따로 합니다.
대조는 조회 전용이며 클러스터·Git을 변경하지 않습니다. 원본 스크립트는 `deploy/shared/scripts/deploy_state.py`입니다.

- [무엇을 비교하나요?](#무엇을-비교하나요)
- [대조 실행](#대조-실행)
- [Worker에서 점검](#worker에서-점검)
- [배포 기록 남기기](#배포-기록-남기기)
- [결과 해석과 조치](#결과-해석과-조치)

## 무엇을 비교하나요?

| 영역 | 비교 내용 | 방법 |
| --- | --- | --- |
| `manifest` | 현재 코드로 만든 적용 대상 리소스와 클러스터의 실제 리소스 | 앱의 기존 렌더 명령 → 배포와 같은 `kubectl apply`를 서버 dry-run으로 계산 → 실제 리소스와 필드 단위 비교 |
| `checkout` | 앱 경로의 미커밋 변경 | `git status`. 미커밋 변경도 비교 기준에 포함되므로 경고로 표시 |
| `record` | 마지막 배포 이후 앱 실행 파일이 바뀌었는지 | 앱 namespace의 ConfigMap `deploy-record-<app>` |
| `input` | 배포에 사용한 외부 env·입력 파일의 SHA-256 | 같은 ConfigMap. 파일 내용은 기록하지 않음 |
| `workload` | 기록 시점과 현재의 워크로드 목록·이미지·Pod template 해시 | `kubectl get` |
| `health` | Ready 수, rollout 진행, CrashLoopBackOff·ImagePullBackOff 등 | `kubectl get` |

`manifest`가 핵심 판정입니다. 배포 기록이 없어도 판정할 수 있습니다. `record`·`workload`는 기록이 있을 때 배포 이후 변화를 보충합니다.

| 앱 | 렌더 원본 | 필요 입력 |
| --- | --- | --- |
| Portal | `kubectl kustomize deploy/portal/k8s/overlays/prod` | 없음 |
| Keycloak | `deploy/keycloak/scripts/up.py --render-output` | `KEYCLOAK_ENV`, 등록된 공용 TLS. `VIP_BACKENDS` 생략 시 현재 배치 보존 |
| FTP | `deploy/ftp/scripts/up.py --render-output` | `FTP_ENV`(생략 시 `deploy/ftp/env/prod.env`) |
| MinIO·Registry | `deploy/<app>/scripts/manage.py render` | `MINIO_ENV`·`REGISTRY_ENV` |
| Airflow·Monitoring·Headlamp | `deploy/<app>/scripts/manage.py render` | `*_ENV`, Helm, 반입한 chart 파일 |

비교에서 제외하거나 따로 표시하는 항목:

- Secret(값), Job·Pod(일회성 실행), Namespace(최초 생성 후 운영 metadata 보존), CRD(Helm이 upgrade하지 않음), Helm hook 리소스. 제외 개수는 결과 요약에 표시합니다.
- 서버가 관리하는 metadata(`resourceVersion`, `managedFields`, revision annotation 등)와 `status`.
- 코드에 선언하지 않고 클러스터에서 추가된 필드(Helm 관리 annotation, `rollout restart` 시각 등)는 배포해도 남으므로 차이로 보지 않습니다.
- `spec.replicas`만 다르면 운영 조정일 수 있어 `WARN`으로 표시합니다.
- 코드에서 리소스를 삭제했지만 클러스터에 남아 있는 리소스는 찾지 않습니다. Helm 앱에서 코드에서 지운 필드도 차이로 나오지 않을 수 있습니다.
- 공용 Traefik·VIP·DNS·TLS 접속과 Keycloak realm·client 같은 앱 내부 설정은 대상이 아닙니다. [접속·기능 검증](02-deploy.md#접속기능-검증)과 앱별 `*-check`로 확인합니다.

## 대조 실행

CP1 저장소 루트에서 실행합니다. 조회 명령입니다. 배포할 때와 같은 env 변수를 지정합니다. Worker에서 실행하는 방법은 [Worker에서 점검](#worker에서-점검)을 따릅니다.

```bash
make drift-check KUBE_CONTEXT=kubernetes-admin@kubernetes                                 # 전체 앱
make drift-check APP=airflow KUBE_CONTEXT=kubernetes-admin@kubernetes AIRFLOW_ENV=<경로>   # 앱 또는 그룹
make drift-check KUBE_CONTEXT=kubernetes-admin@kubernetes DRIFT_JSON=1                    # agent·자동화용 JSON
make drift-check KUBE_CONTEXT=kubernetes-admin@kubernetes DRIFT_SKIP_MANIFEST=1           # 리소스 비교 생략
```

| 종료 코드 | 의미 |
| --- | --- |
| `0` | 모든 대상이 현재 코드와 일치하고 Ready |
| `1` | `DRIFT` 또는 `WARN`이 하나 이상 있음 |
| `2` | 불일치는 없지만 판정할 수 없는 항목이 있음(렌더 실패·기록 없음·조회 실패), 또는 입력 오류 |

**기대 결과:** 앱마다 `OK manifest 리소스 N/N개 일치`가 표시되고 종료 코드가 `0`입니다.

**실패 확인:** `UNKNOWN manifest 현재 코드 렌더 실패`면 표시된 오류를 해당 앱의 `*-check`로 재현합니다. env 경로·Helm·chart 파일·공용 TLS 등록이 흔한 원인입니다.

## Worker에서 점검

Worker `khinfow01`에서 opencode `ops-check` agent로 같은 대조를 실행합니다. 배포·배포 기록은 CP1에서 합니다.

1. **kubeconfig:** CP1의 admin kubeconfig를 승인된 수단으로 khinfow01 실행 계정의 `~/.kube/config`(권한 `0600`)에 둡니다. context는 `kubernetes-admin@kubernetes`입니다.
2. **저장소:** 사내 GitHub에서 clone하고 `git sparse-checkout set --no-cone '/*' '!/.claude/' '!/.codex/'`로 개발 agent 폴더를 제외합니다. 갱신은 사용자가 CP1과 같은 commit으로 맞춥니다.
3. **도구:** `kubectl`, `python3`, 각 chart lock의 버전 이상인 `helm`. kubeconfig의 API server 주소 6443 포트에 접근할 수 있어야 합니다.
4. **chart:** Git에서 제외된 `deploy/<app>/helm/vendor/*.tgz`를 준비합니다. 사내 미러에 접근되면 `python3 deploy/airflow/scripts/manage.py fetch-chart`, `python3 deploy/monitoring/scripts/manage.py fetch-chart`, `make headlamp-fetch-chart`, 아니면 CP1의 같은 파일을 복사합니다.
5. **env:** CP1 배포에 쓰는 외부 env를 같은 권한(`0600`)으로 두고 경로를 [운영 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다.
6. **확인:** `kubectl --context kubernetes-admin@kubernetes get nodes`가 성공하면 `make drift-check KUBE_CONTEXT=kubernetes-admin@kubernetes`를 실행합니다.

admin kubeconfig는 클러스터 전체 권한이며 kubeadm 인증서는 개별 폐기가 어렵습니다. khinfow01에서는 클러스터 변경 명령을 거부하는 `ops-check` agent만 사용하고, 파일을 다른 위치로 복사하지 않습니다.

## 배포 기록 남기기

`make <app>-up`(keycloak·minio·registry·airflow·monitoring·headlamp·ftp)은 배포가 성공하면 자동으로 기록합니다.
`kubectl apply -k`나 `python3 deploy/<app>/scripts/manage.py deploy`처럼 직접 배포했다면 배포·rollout 완료 직후 기록합니다.

```bash
make deploy-record APP=portal KUBE_CONTEXT=kubernetes-admin@kubernetes RECORD_INPUTS="/appdata/etchax-config/portal/api.env"
```

| 입력 | 설명 |
| --- | --- |
| `APP` | `apps.json`의 앱 이름 하나 |
| `KUBE_CONTEXT` | 배포한 context. 현재 kubectl context에 의존하지 않음 |
| `RECORD_INPUTS` | 저장소 밖 입력 파일(공백 구분). 생략 가능. 경로에 공백이 없어야 함 |

**기대 결과:** `배포 기록 저장: <namespace>/deploy-record-<app> commit=<12자리>`가 출력됩니다. 미커밋 변경을 포함해 배포했으면 `(미커밋 변경 포함)`이 붙습니다.

**실패 확인:** namespace가 없으면 배포가 끝나지 않은 것입니다. env로 namespace를 바꾼 설치는 `python3 deploy/shared/scripts/deploy_state.py record <app> --context "$KUBE_CONTEXT" --namespace <namespace>`로 기록합니다. 대조는 모든 namespace에서 기록을 찾습니다.

## 결과 해석과 조치

| 표시 | 의미 | 조치 |
| --- | --- | --- |
| `DRIFT manifest ... 현재 코드와 다름: <필드>` | 현재 코드를 적용하면 표시된 필드가 바뀜 | 코드가 의도한 최신 상태면 앱별 배포. 클러스터 값이 맞다면 저장소 수정 필요(사내에서는 보고) |
| `DRIFT manifest ... 클러스터에 없음` | 코드에 있는 리소스가 배포되지 않았거나 namespace가 없음 | 앱 설치·배포 여부 확인 |
| `DRIFT manifest ... 적용할 수 없음` | 변경 불가 필드(StatefulSet volumeClaimTemplates, PVC 용량 축소 등) 차이 | 앱 문서의 재생성·이전 절차 확인. 자동으로 삭제·재생성하지 않음 |
| `WARN manifest replica 수` | 실제 replica가 코드와 다름 | 의도한 운영 조정인지 확인 |
| `WARN checkout 미커밋 변경` | CP1에서 앱 파일을 직접 수정함. 이 내용이 비교 기준에 포함됨 | 내용을 확인하고 저장소에 반영하거나 담당자와 정리. 강제 초기화하지 않음 |
| `DRIFT record 앱 정의가 바뀜` | 마지막 배포 이후 checkout의 앱 실행 파일이 바뀜 | `manifest` 결과와 함께 판단. manifest가 일치하면 렌더 결과에 영향 없는 변경 |
| `DRIFT input` | 배포 후 외부 env·입력 파일이 바뀜 | 의도한 변경이면 env 검사 → Secret 갱신 → 앱 재배포 |
| `DRIFT workload` | 기록 이후 클러스터에서 이미지·template이 바뀌었거나 워크로드가 사라짐 | `kubectl rollout history`·events로 수동 변경 여부 확인 |
| `WARN health` | Ready 부족·rollout 진행·이미지 pull·반복 재시작 | [장애 조회](03-operations.md#장애-조회--cp1) |
| `UNKNOWN record 배포 기록 없음` | 기록 기능 이전 배포이거나 미배포 | manifest가 일치하면 `make deploy-record`로 기준을 남김 |
| `UNKNOWN manifest`·`query` | 렌더·context·권한·kubectl 오류 | 표시된 오류와 `kubectl --context "$KUBE_CONTEXT" get ns`로 접근 확인 |

대조 결과는 실제 서버 조회 근거입니다. 운영값이 [인프라 정보](../infrastructure/README.md)의 현재 값과 다르면 해당 원본을 `서버 조회` 상태로 갱신하고, 남은 서버 작업은 [서버 적용 대기 작업](../infrastructure/pending.md)에 반영합니다.
