# 기존 클러스터에 MinIO만 추가

[Portal 배포 안내](README.md) · [공용 Ingress 안내](../shared/ingress/README.md)

MinIO가 아직 없는 환경의 최초 설치 절차입니다. 3단계에서 Deployment와 초기화 Job을 새로 생성합니다.

명령은 저장소 루트에서 실행합니다. 변경 파일을 먼저 서버 저장소에 전달합니다.

- 배포 범위: `tailwind-internal` namespace에 MinIO만 추가합니다. Portal·Keycloak 전체 스택은 재배포하지 않습니다.
- 재사용할 구성: 공용 Traefik(`etch-sso/traefik`)과 Headlamp의 `etch.samsungds.net` 인증서입니다.
- 실행 노드: MinIO와 초기화 Job 모두 `khplanew01`(`10.172.40.117`)에 배치합니다.

`khplane01w09`(`10.172.40.87`)는 사용자 지정 Keycloak 전용 Worker입니다. MinIO는 이 노드에 배치하지 않습니다.

## 1. 대상과 저장소 확인

```bash
export KUBE_CONTEXT='<실제 운영 context>'
kubectl config use-context "$KUBE_CONTEXT"
kubectl get node khplanew01 -o wide -L kubernetes.io/hostname
kubectl get storageclass
kubectl get pv
kubectl -n etch-sso get deployment traefik
kubectl -n headlamp get ingress headlamp
```

`khplanew01`의 InternalIP가 `10.172.40.117`, hostname 라벨이 `khplanew01`이며 Ready인지 확인합니다.
기본 MinIO PVC는 10Gi·ReadWriteOnce입니다. 다음 중 하나를 먼저 준비합니다.

- `khplanew01`에서 사용할 수 있는 StorageClass를 통한 동적 볼륨 생성
- 이 PVC와 결합할 수 있는 PV

로컬 PV를 사용하면 실제 디스크 경로와 PV의 nodeAffinity를 `khplanew01`에 맞춥니다.
다른 서버의 로컬 PV를 연결하면 Pod는 Pending이 됩니다.
Worker 디스크 경로는 아직 정하지 않았으며 이 절차가 PV를 자동 생성하지 않습니다.
특정 StorageClass를 사용하면 `k8s/base/minio.yaml`의 PVC에 해당 `storageClassName`을 지정합니다.
저장소를 준비하지 않은 상태에서는 Pod가 실행되지 않습니다.

기본 YAML은 다음 두 릴리스로 고정합니다. Worker가 두 이미지를 모두 받을 수 있어야 합니다.

| 용도 | 반입할 이미지 | 릴리스 원본 |
| --- | --- | --- |
| MinIO 서버·콘솔 | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | [서버 릴리스](https://github.com/minio/minio/releases/tag/RELEASE.2025-09-07T16-13-09Z) |
| 버킷 초기화 도구 | `minio/mc:RELEASE.2025-08-13T08-35-41Z` | [mc 릴리스](https://github.com/minio/mc/releases/tag/RELEASE.2025-08-13T08-35-41Z) |

릴리스 고정은 실제 이미지 접근·기동 검증과 별개입니다. 원본 registry에서 받을 수 없으면
사내에 보관한 해당 릴리스의 이미지 또는 같은 소스로 빌드·검증한 이미지를 준비합니다.
두 image를 반입한 registry 주소와 고유 태그 또는 digest로 바꾸고 `latest`는 사용하지 않습니다.
운영 overlay도 이 기본 YAML을 참조합니다. 변경 후 `make server-check APP=portal`로 렌더를 검사하고,
선택한 Worker의 실제 이미지 pull·서버와 초기화 도구의 동작은 아래 3단계에서 확인합니다.

## 2. namespace와 MinIO 계정 입력

```bash
kubectl apply -f deploy/portal/k8s/overlays/prod/namespace.yaml
```

`deploy/portal/env/prod/minio.env`에서 관리자 계정·비밀번호를 실제 값으로 설정합니다.
주소는 다음과 같습니다.

```dotenv
MINIO_BROWSER_REDIRECT_URL=https://etch.samsungds.net/minio-console/
MINIO_SERVER_URL=http://minio:9000
```

`MINIO_ACCESS_KEY`·`MINIO_SECRET_KEY`는 API에서 사용할 계정의 입력이며 계정 생성 명령이 아닙니다.
처음에는 `MINIO_ROOT_USER`·`MINIO_ROOT_PASSWORD`로 로그인할 수 있습니다.
별도 운영자·API 계정은 기동 후 `mc`로 생성하고 필요한 정책을 부여합니다.

```bash
make env-check APP=portal PROFILE=prod COMPONENT=minio
make k8s-env APP=portal PROFILE=prod COMPONENT=minio KUBE_CONTEXT="$KUBE_CONTEXT"
```

이 Secret 등록 명령은 현재 kubectl context를 사용하므로 1단계의 선택을 유지합니다.

## 3. MinIO 생성

```bash
kubectl -n tailwind-internal apply -f deploy/portal/k8s/base/minio.yaml
kubectl -n tailwind-internal get pvc minio-data
kubectl -n tailwind-internal rollout status deployment/minio --timeout=5m
kubectl -n tailwind-internal wait --for=condition=complete job/minio-init --timeout=5m
kubectl -n tailwind-internal logs job/minio-init
kubectl -n tailwind-internal get pods -l app.kubernetes.io/name=minio -o wide
kubectl -n tailwind-internal get pods -l app.kubernetes.io/name=minio-init -o wide
```

다음 상태를 모두 확인합니다.

- PVC: `Bound`
- Deployment: `Available`
- 초기화 Job: `Complete`
- 두 Pod의 `NODE`: `khplanew01`

배포 YAML의 nodeSelector는 단독 apply에도 적용됩니다.
MinIO Deployment는 Recreate 전략으로 기존 Pod를 종료한 뒤 새 Pod를 시작합니다.
`minio-init`은 `emails`, `profile` 버킷을 준비합니다.

Pending이면 `kubectl -n tailwind-internal describe pvc minio-data`와 Pod 이벤트를 확인합니다.

### 초기화 재시도와 명령 변경

초기화 Job은 연결 대기를 포함해 300초 안에 완료해야 합니다. 최초 설치에서 이미지 반입이나
스토리지 준비가 지연돼 실패하면 먼저 원인을 해결하고 MinIO Deployment가 Available인지 확인합니다.

기존 Job에 새 명령을 apply하면 Pod template이 불변 필드여서 거부됩니다.
실패 후 재시도하거나 초기화 명령을 변경했을 때는 아래 순서로 해당 Job을 다시 생성합니다.
최초 설치에는 위 생성 명령을 사용합니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal describe job minio-init
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal logs job/minio-init --tail=100
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal rollout status deployment/minio --timeout=5m
```

원인을 해결한 뒤 실행합니다. 완료·실패로 종료됐고 활성 Pod가 없는 Job만 재생성합니다.
진행 중이면 종료 상태가 될 때까지 기다립니다. 삭제 대상은 초기화 Job이며 PVC와 버킷 데이터는 보존됩니다.

```bash
kubectl --context "$KUBE_CONTEXT" -n tailwind-internal get job minio-init -o json |
  python3 -c 'import json,sys; j=json.load(sys.stdin); s=j.get("status", {}); done=any(c.get("type") in ("Complete", "Failed") and c.get("status")=="True" for c in s.get("conditions", [])); sys.exit(0 if done and not s.get("active", 0) else "초기화 Job이 아직 종료되지 않았습니다.")' &&
  kubectl --context "$KUBE_CONTEXT" -n tailwind-internal delete job minio-init --wait=true &&
    kubectl --context "$KUBE_CONTEXT" -n tailwind-internal apply -f deploy/portal/k8s/base/minio.yaml
```

재생성 후 `job/minio-init`의 Complete 상태와 로그를 다시 확인합니다. 이미 있는 버킷은 유지합니다.

## 4. 기존 인증서 재사용

Headlamp Ingress가 실제로 `headlamp/headlamp-tls`를 사용하며 도메인이 일치하는지 확인합니다.
다른 Secret을 사용하면 아래 조회 이름을 해당 이름으로 바꿉니다.

Secret은 다른 namespace에서 직접 참조할 수 없으므로 복사합니다.
이미 유효한 `tailwind-internal/portal-tls`가 있으면 이 단계는 생략합니다.

```bash
kubectl -n headlamp get secret headlamp-tls -o json |
  python3 -c 'import json,sys; s=json.load(sys.stdin); print(json.dumps({"apiVersion":"v1","kind":"Secret","metadata":{"name":"portal-tls","namespace":"tailwind-internal"},"type":s["type"],"data":s["data"]}))' |
  kubectl apply -f -
```

원본 인증서가 갱신되면 복사본도 갱신합니다. 인증서·개인키를 터미널에 출력하거나 Git에 추가하지 않습니다.

## 5. 공용 Traefik에 MinIO 경로 설정

```bash
kubectl -n tailwind-internal apply -f deploy/portal/k8s/overlays/prod/traefik-rbac.yaml
kubectl -n etch-sso apply -k deploy/shared/ingress/middlewares
kubectl -n etch-sso get deployment traefik -o yaml
kubectl -n etch-sso edit deployment traefik
```

ConfigMap 생성 출력의 `traefik-middlewares-<해시>` 이름을 기록합니다.
기존 Deployment의 다음 부분만 편집하고 이미지·replica·배치·hostPort·ServiceAccount 등은 유지합니다.

- `spec.template.spec.containers`에서 `name: traefik`인 컨테이너의 기존 args 끝에
  `--providers.file.directory=/etc/traefik/dynamic`와 `--providers.file.watch=true`를 추가합니다.
  이미 있으면 중복 추가하지 않습니다. 다른 file provider 디렉터리를 사용 중이면 먼저 설정을 통합합니다.
- `--providers.kubernetesingress.namespaces=`가 명시되어 있고 값이 비어 있지 않으면 기존 목록에
  `tailwind-internal`을 추가합니다. 이미 포함돼 있거나 전체 namespace 감시 상태라면 유지합니다.
- 같은 컨테이너의 `volumeMounts`와 Pod의 `volumes`에 아래 항목을 추가합니다.
  이미 있으면 새 ConfigMap 이름과 일치하는지 확인합니다.

```yaml
# spec.template.spec.containers의 traefik 항목 아래
volumeMounts:
  - name: middlewares
    mountPath: /etc/traefik/dynamic
    readOnly: true

# spec.template.spec 아래
volumes:
  - name: middlewares
    configMap:
      name: traefik-middlewares-<생성 출력의 실제 해시>
```

```bash
kubectl -n etch-sso rollout status deployment/traefik --timeout=5m
```

공용 Traefik의 재기동이 발생합니다. 이후 Headlamp 등 기존 앱 접속도 확인합니다.

이 설정은 공용 배포 원본에도 반영되어 있으며 이후 재배포는 기존 감시·VIP를 보존하는
지원 도구를 사용합니다. `deploy/shared/ingress` 전체를 직접 apply해 기존 배치를 덮어쓰지 않습니다.

## 6. 콘솔 Ingress와 접속

`k8s/overlays/prod/minio-console-ingress.yaml`의 두 예시 도메인을 `etch.samsungds.net`으로 변경합니다.
TLS Secret은 앞서 준비한 `portal-tls`를 사용합니다.

```bash
kubectl -n tailwind-internal apply -f deploy/portal/k8s/overlays/prod/minio-console-ingress.yaml
kubectl -n tailwind-internal get pods,pvc,ingress
```

`https://etch.samsungds.net/minio-console/`에 접속해 MinIO 계정으로 로그인합니다.
로그인·새로고침·버킷 조회·파일 업로드/다운로드와 기존 Headlamp 접속을 확인합니다.
라우팅 오류는 `kubectl -n etch-sso logs deployment/traefik --tail=100`으로 확인합니다.

이 설치는 콘솔만 공개합니다. 다른 Pod가 S3 API에 연결할 때는 다음 주소를 사용합니다.

| 접속하는 Pod의 위치 | S3 API 주소 |
| --- | --- |
| 같은 namespace | `http://minio:9000` |
| 다른 namespace | `http://minio.tailwind-internal.svc:9000` |

외부 S3 API나 Portal 연동은 별도 경로·API 계정 설정이 필요합니다.

공식 참고: [Kubernetes 영구 저장소](https://kubernetes.io/docs/concepts/storage/persistent-volumes/),
[Traefik File provider](https://doc.traefik.io/traefik/reference/install-configuration/providers/others/file/),
[MinIO 서버·콘솔 URL 처리](https://github.com/minio/minio/blob/RELEASE.2025-09-07T16-13-09Z/cmd/common-main.go).
