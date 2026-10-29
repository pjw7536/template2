# 처음 사용하는 Kubernetes 명령어 모음

Kubernetes(K8s)는 컨테이너로 실행하는 앱을 여러 서버에 배치하고 관리하는 도구입니다. 이 문서는 `kubectl`로 상태를 확인하고, 로그를 읽고, 앱을 관리할 때 참고하는 입문용 명령어 모음입니다.

## 1. 시작 전 준비와 예시 읽는 법

- PC 또는 작업 서버에 `kubectl`이 설치되어 있어야 합니다.
- 접속할 클러스터의 kubeconfig와 계정 권한이 필요합니다. 기본 설정 위치는 `~/.kube/config`이며, 설치만으로 클러스터에 연결되지는 않습니다.
- 아래 `demo`, `web`, `web-abc123`, `app.yaml`은 예시입니다. 실제 Namespace, Deployment, Pod, 파일 이름으로 바꾸세요. 예시 리소스는 자동으로 생성되지 않습니다.
- 코드 블록은 필요한 명령어를 골라 실행하세요. 특히 **변경**·**삭제** 절은 한꺼번에 실행하는 실습 스크립트가 아닙니다.

이 저장소의 환경 구성과 실행은 [서버 배포 안내](../../../deploy/README.md), [로컬 환경 안내](../../../local/README.md)의 Makefile 진입점을 따르세요. 아래는 환경과 무관하게 사용하는 일반 명령어입니다.

## 2. 꼭 알아둘 용어

| 용어 | 의미 | 조회할 때 쓰는 이름 / 약어 |
| --- | --- | --- |
| Cluster | Kubernetes가 관리하는 서버와 제어 시스템 전체 | 현재 접속 대상은 `config current-context`로 확인 |
| Context | 클러스터·사용자·기본 Namespace를 묶은 접속 설정 | `config get-contexts` |
| Node | Pod가 실행되는 서버 | `nodes` / `no` |
| Namespace | 리소스를 나눠 관리하는 논리적 공간 | `namespaces` / `ns` |
| Pod | 컨테이너 하나 이상을 함께 실행하는 기본 단위 | `pods` / `po` |
| Deployment | 앱의 Pod 개수와 배포 버전을 관리 | `deployments` / `deploy` |
| StatefulSet | 고정된 식별자와 저장소가 필요한 앱의 Pod 관리 | `statefulsets` / `sts` |
| Service | Pod에 접근하는 일정한 주소와 포트 제공 | `services` / `svc` |
| Ingress | HTTP/HTTPS 요청의 호스트·경로별 연결 규칙 | `ingresses` / `ing` |
| ConfigMap / Secret | 앱 설정 / 비밀번호 등 민감한 설정 | `configmaps` / `cm`, `secrets` |
| PVC | 앱이 사용할 영구 저장소 요청 | `persistentvolumeclaims` / `pvc` |
| Job / CronJob | 완료되는 작업 / 주기적으로 실행할 작업 | `jobs`, `cronjobs` / `cj` |

Ingress 규칙이 실제로 동작하려면 해당 규칙을 처리하는 Ingress Controller가 필요합니다.

## 3. 명령어 기본 형태

```text
kubectl [동작] [리소스 종류] [리소스 이름] [옵션]
```

```bash
# demo 공간에 있는 Pod 목록 조회
kubectl get pods -n demo

# 특정 Pod의 상세 상태 조회
kubectl describe pod web-abc123 -n demo
```

| 옵션 | 의미 | 예시 |
| --- | --- | --- |
| `-n` | 특정 Namespace 지정 | `-n demo` |
| `-A` | 모든 Namespace 조회 | `kubectl get pods -A` |
| `-o wide` | IP, 배치된 Node 등 추가 정보 | `kubectl get pods -n demo -o wide` |
| `-o yaml` | YAML 형식의 상세 설정 | `kubectl get deployment web -n demo -o yaml` |
| `-w` | 변경 사항을 계속 관찰 | `kubectl get pods -n demo -w` |
| `-l` | 라벨로 대상 필터링 | `kubectl get pods -n demo -l app=web` |
| `--context` | 이번 명령의 접속 설정 지정 | `kubectl --context dev get pods -n demo` |

`app=web` 라벨이 실제로 있어야 필터 결과가 나옵니다. `-w`, `logs -f`, `port-forward`는 `Ctrl+C`로 종료합니다.

## 4. 접속 대상 확인하기

```bash
# 설치된 kubectl 버전
kubectl version --client

# 등록된 접속 설정과 현재 접속 대상
kubectl config get-contexts
kubectl config current-context

# 클러스터 연결 정보와 서버 상태
kubectl cluster-info
kubectl get nodes
kubectl get namespaces
```

**로컬 설정 변경:** 아래 명령은 이후 명령의 접속 대상 또는 기본 Namespace를 바꿉니다. `dev`와 `demo`를 실제 이름으로 바꾸세요.

```bash
kubectl config use-context dev
kubectl config set-context --current --namespace=demo
```

기본 Namespace가 지정되지 않으면 보통 `default`를 사용합니다. 이 문서는 대상을 알아보기 쉽도록 `-n demo`를 명시합니다. Node처럼 클러스터 전체에 속하는 리소스는 Namespace로 나뉘지 않습니다.

## 5. 앱 상태 조회하기

```bash
# Namespace를 모를 때 전체 Pod에서 확인
kubectl get pods -A

# 앱의 배포 상태와 실행 중인 Pod
kubectl get deployments -n demo
kubectl get pods -n demo -o wide
kubectl get pods -n demo --show-labels

# 네트워크 연결과 저장소
kubectl get services,ingresses -n demo
kubectl get pvc -n demo

# 설정 목록과 배치 작업
kubectl get configmaps,secrets -n demo
kubectl get jobs,cronjobs -n demo

# 대표 리소스를 한 번에 조회
kubectl get all -n demo
```

`get all`은 모든 종류의 리소스를 보여주지 않습니다. ConfigMap, Secret, PVC, Ingress 등은 따로 조회하세요. Secret 목록 조회는 값 자체를 표시하지 않지만, 상세 YAML에는 민감한 값이 담길 수 있으므로 공유하지 마세요.

Pod 목록은 다음 순서로 읽으면 좋습니다.

| 항목 / 표시 | 읽는 방법 |
| --- | --- |
| `READY`가 `1/1` | 표시된 컨테이너 1개 중 1개가 준비됨 |
| `READY`가 `0/1` | 실행 여부와 별개로 아직 요청을 처리할 준비가 안 됨 |
| `STATUS`가 `Running` | Pod가 실행 단계에 있음. 앱의 정상 응답까지 보장하지는 않음 |
| `Pending` | 배치 또는 볼륨 준비 등을 기다림. Events 확인 |
| `ContainerCreating` | 이미지·네트워크·볼륨 등 컨테이너 실행 준비 중 |
| `CrashLoopBackOff` | 컨테이너가 반복 종료되어 재시도 대기 중 |
| `ImagePullBackOff` / `ErrImagePull` | 이미지 다운로드 실패. 이름·태그·인증·네트워크 확인 |
| `Completed` | 작업용 컨테이너가 정상 종료됨. Job에서는 정상일 수 있음 |
| `RESTARTS` | 컨테이너 재시작 횟수. 계속 증가하면 로그 확인 |

## 6. 상세 상태와 로그 확인하기

```bash
# 설정, 상태, 하단 Events 확인
kubectl describe pod web-abc123 -n demo
kubectl describe deployment web -n demo

# Namespace 이벤트를 생성 시간 순서로 확인
kubectl get events -n demo --sort-by=.metadata.creationTimestamp

# 최근 로그 100줄 / 최근 10분 / 실시간 로그
kubectl logs web-abc123 -n demo --tail=100
kubectl logs web-abc123 -n demo --since=10m
kubectl logs web-abc123 -n demo -f --tail=100

# 같은 Pod에서 직전에 종료된 컨테이너의 로그
kubectl logs web-abc123 -n demo --previous

# Pod 내 컨테이너 이름 확인 후 특정 컨테이너 로그 조회
kubectl get pod web-abc123 -n demo -o jsonpath='{.spec.containers[*].name}'
kubectl logs web-abc123 -n demo -c web --tail=100
```

컨테이너가 여러 개라면 `-c 실제컨테이너이름`을 사용하세요. `--previous`는 삭제된 Pod의 로그를 복구하는 명령이 아니며, 이전 실행 로그가 남아 있어야 조회됩니다. 로그와 이벤트는 영구 보관 자료가 아닙니다.

## 7. 컨테이너 접속과 내 PC에서 접속하기

```bash
# 컨테이너 안에서 셸 실행, 종료는 exit
kubectl exec -it web-abc123 -n demo -c web -- /bin/sh

# 셸 접속 없이 명령 하나 실행
kubectl exec web-abc123 -n demo -c web -- pwd

# 내 PC의 8080 포트를 Service의 80 포트로 연결
kubectl port-forward -n demo service/web 8080:80
```

`exec`의 `--` 뒤는 컨테이너 안에서 실행할 명령입니다. 이미지에 셸이나 해당 명령이 없으면 실행되지 않습니다. 컨테이너 안에서 파일을 바꿔도 Pod 교체 후 유지되지 않을 수 있습니다.

`port-forward`의 오른쪽 `80`은 실제 Service 포트로 바꾸세요. 실행한 컴퓨터에서 `http://localhost:8080`으로 접속합니다. 기본적으로 로컬 주소에만 연결되며, 터미널을 종료하면 연결도 끝납니다. 서버에서 명령을 실행했다면 `localhost`는 그 서버를 뜻합니다.

## 8. CPU·메모리와 권한 확인하기

```bash
kubectl top nodes
kubectl top pods -n demo
kubectl top pods -n demo --containers

# 현재 계정이 해당 작업을 할 수 있는지 확인
kubectl auth can-i get pods -n demo
kubectl auth can-i create deployments -n demo
```

`top`은 Metrics Server 등 리소스 메트릭 API를 제공하는 구성 요소가 있어야 동작합니다. `Metrics API not available`은 앱 자체의 장애를 뜻하지 않습니다. `Forbidden`은 계정 권한 확인이 필요하다는 뜻입니다.

## 9. YAML 확인과 적용 — 클러스터 변경

Manifest는 원하는 리소스 상태를 적은 YAML 파일입니다. `app.yaml`을 실제 준비된 파일 경로로 바꾸세요. 적용 전 Context와 Namespace를 확인하세요.

```bash
# 현재 상태와 파일의 차이 확인
kubectl diff -n demo -f app.yaml

# 서버에서 요청을 검증하되 리소스는 저장하지 않음
kubectl apply -n demo -f app.yaml --dry-run=server

# 실제 생성 또는 변경
kubectl apply -n demo -f app.yaml

# Deployment 적용 진행 상황 확인
kubectl rollout status deployment/web -n demo --timeout=120s
```

`diff`의 종료 코드 `1`은 차이가 있다는 뜻이고, `1`보다 크면 오류입니다. dry-run도 서버 연결과 권한이 필요하며, 성공하더라도 앱 기동까지 보장하지 않습니다. 파일에 `metadata.namespace`가 있다면 `-n`과 일치하는지 확인하세요. `-n`은 Namespace 자체를 생성하지 않습니다.

Kustomize 디렉터리(`kustomization.yaml`이 있는 폴더)를 사용할 때는 `-f` 대신 `-k`를 사용합니다. 아래 경로도 예시입니다.

```bash
kubectl kustomize ./overlays/dev
kubectl diff -k ./overlays/dev
kubectl apply -k ./overlays/dev
```

렌더링 결과에 Secret이 포함될 수 있습니다. 저장소에서 관리하는 배포는 해당 배포 문서의 절차를 우선하세요.

## 10. 재시작·개수 조절·되돌리기 — 클러스터 변경

### Deployment의 Pod 다시 시작하기

```bash
kubectl rollout restart deployment/web -n demo
kubectl rollout status deployment/web -n demo --timeout=120s
```

Deployment의 배포 전략에 따라 Pod를 교체합니다. 복제본 수, 준비 상태 검사, 자원 여유에 따라 서비스가 잠시 중단될 수 있습니다. 대기 시간 초과는 배포 취소를 의미하지 않으므로 Pod와 Events를 확인하세요.

### Pod 개수 변경하기

```bash
kubectl scale deployment/web -n demo --replicas=2
kubectl get deployment web -n demo
```

`--replicas=0`은 해당 Deployment의 Pod를 모두 내려 서비스가 중단될 수 있습니다. HPA나 GitOps가 관리한다면 수동 변경이 다시 덮어써질 수 있고, YAML의 복제본 수도 다음 적용 때 영향을 줍니다.

### 배포 이력 조회와 이전 버전 복구

```bash
kubectl rollout history deployment/web -n demo

# 변경: 보관된 이전 리비전으로 되돌림
kubectl rollout undo deployment/web -n demo
kubectl rollout status deployment/web -n demo --timeout=120s
```

이전 리비전이 보관되어 있어야 복구할 수 있습니다. Deployment의 Pod 템플릿을 되돌리는 것이므로 DB 데이터, 별도로 수정한 ConfigMap·Secret까지 복구하지는 않습니다. 관리 중인 YAML도 원하는 상태에 맞춰야 합니다.

## 11. 리소스 삭제 — 서비스에 영향

삭제 전 `get`으로 대상 이름과 Namespace를 확인하세요. 아래는 서로 다른 삭제 방법의 예시입니다.

```bash
# 단일 Pod 삭제
kubectl delete pod web-abc123 -n demo

# Deployment와 그 Deployment가 관리하는 Pod 삭제
kubectl delete deployment web -n demo

# 파일에 정의된 리소스 삭제
kubectl delete -n demo -f app.yaml
```

Deployment 등이 관리하는 Pod만 지우면 관리자가 원하는 개수를 맞추기 위해 새 Pod를 생성합니다. Deployment를 지워도 별도의 Service와 PVC가 함께 지워지는 것은 아닙니다. `delete -f`는 적용 취소나 이전 버전 복구가 아니라 파일에 적힌 리소스의 삭제입니다.

Namespace 삭제는 그 안의 리소스를 함께 삭제합니다. PVC 삭제는 저장소 정책에 따라 실제 데이터 삭제로 이어질 수 있으므로 일반적인 재시작 방법으로 사용하지 마세요.

## 12. 문제가 생기면 이 순서로 확인하기

1. `kubectl config current-context`로 올바른 클러스터인지 확인합니다.
2. `kubectl get pods -n demo -o wide`로 Pod 이름, 준비 상태, 재시작 횟수를 확인합니다.
3. `kubectl describe pod web-abc123 -n demo`의 상태와 Events를 확인합니다.
4. `kubectl logs web-abc123 -n demo --tail=100`으로 앱 오류를 확인합니다. 반복 재시작 중이면 `--previous`도 확인합니다.
5. 앱이 실행되는데 연결이 안 되면 아래로 Service의 selector·포트와 실제 연결 대상을 확인합니다.

```bash
kubectl describe service web -n demo
kubectl get endpointslices -n demo -l kubernetes.io/service-name=web
kubectl get ingresses -n demo
```

EndpointSlice에 준비된 연결 대상이 없다면 Service selector와 Pod 라벨, Pod의 준비 상태를 확인하세요. PVC가 `Pending`이면 `kubectl describe pvc 실제PVC이름 -n demo`에서 이벤트를 확인하세요.

| 메시지 | 먼저 확인할 내용 |
| --- | --- |
| `No resources found` | Context, Namespace, 라벨 필터가 맞는지 |
| `NotFound` | 리소스 종류와 이름, Namespace가 맞는지 |
| `Unauthorized` | kubeconfig 인증 정보 또는 로그인 만료 여부 |
| `Forbidden` | 현재 계정에 작업 권한이 있는지 |
| 연결 거부 / 시간 초과 | kubeconfig의 접속 대상, VPN·네트워크, API 서버 상태 |

## 13. 도움말과 공식 참고 문서

```bash
kubectl --help
kubectl logs --help
kubectl explain deployment
kubectl explain deployment.spec.template.spec.containers
kubectl api-resources
```

- [kubectl 빠른 참조](https://kubernetes.io/docs/reference/kubectl/quick-reference/): 조회·로그·접속·리소스 관리 예시
- [kubectl 명령어 참조](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands.html): 명령별 옵션과 동작
- [Deployment 동작 설명](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/): 배포와 롤백의 범위
