# Registry 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.
원본 문서: [README](../../../../deploy/registry/README.md) · [설치](../../../../deploy/registry/docs/01-install.md) · [운영](../../../../deploy/registry/docs/02-operations.md). 이 런북과 다르면 원본이 우선입니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `registry` |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/registry` |
| 주소 | `http://registry.etch.samsungds.net` (HTTP, TLS 없음) |
| 배포 명령 | `make registry-check` → `make registry-up` (성공 시 배포 기록 자동) |
| 완료 기준 | PVC `Bound`, Deployment `Available`, 사람이 빌드 host push·다른 노드 pull 확인 |
| 먼저 필요한 것 | 공용 Traefik, DNS, 저장 폴더, push 계정 Secret |

## 사람이 해야 하는 일

- [사람] DNS `registry.etch.samsungds.net` → APP VIP
- [사람] khplanew01에서 `sudo install -d -o 1000 -g 1000 -m 0750 /appdata/registry`
- [사람] push 계정 Secret 생성(비밀번호 입력, [설치 4절](../../../../deploy/registry/docs/01-install.md))
- [사람] 모든 노드와 빌드 host의 containerd HTTP 허용 설정(sudo)
- [사람] 빌드 host push·다른 노드 pull 검증, 시험 이미지 삭제

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `REGISTRY_ENV` | Registry env 경로 | `deploy/registry/env/k8s.env` |
| env 키 | `NODE_NAME`, `REGISTRY_IMAGE`, `IMAGE_PULL_SECRET`, `REGISTRY_HOST`, `DATA_HOST_PATH`, `STORAGE_SIZE` | |
| Secret | `registry/registry-htpasswd`(키 `htpasswd`) | 사람이 생성 |

## A. 최초 설치

1. [사람] DNS와 `/appdata/registry` 폴더 준비를 사용자에게 확인합니다.
2. [검사] 배포 전 검사
   ```bash
   make registry-check KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `registry 입력·노드·저장소·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` 신규 설치면 PV·namespace 생성 예정 안내가 함께 나옵니다.
3. [변경] namespace 생성(승인 필요)
   ```bash
   make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   **최초 실행은 의도적으로 실패 종료합니다.** `registry namespace를 만들었습니다. Secret registry-htpasswd을 만든 뒤 up을 다시 실행하세요.`가 나오면 정상이며 다음 단계로 갑니다.
4. [사람] push 계정 Secret 생성을 사용자에게 요청합니다([설치 4절](../../../../deploy/registry/docs/01-install.md)). 완료 후 확인합니다.
   ```bash
   kubectl --context kubernetes-admin@kubernetes -n registry get secret registry-htpasswd
   ```
5. [변경] 배포(승인 필요). Traefik 감시 범위가 바뀌어 Traefik이 재기동됩니다.
   ```bash
   make registry-up KUBE_CONTEXT=kubernetes-admin@kubernetes
   ```
   성공: `registry 배포 완료: http://registry.etch.samsungds.net/v2/`와 `배포 기록 저장: registry/deploy-record-registry`.
6. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
7. [사람] containerd HTTP 허용 설정과 push·pull 검증을 요청합니다([설치 6·7절](../../../../deploy/registry/docs/01-install.md)).

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지 태그 | A-2 → A-5 → C. `registry-up`은 매번 재시작함 |
| push 계정 교체 | 멈추고 사람에게 묻기(빌드 host 재로그인 필요) |
| 이미지 태그 삭제 | 사람만. 되돌릴 수 없음 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n registry get pods,pvc -o wide
kubectl --context kubernetes-admin@kubernetes -n registry logs deployment/registry --tail=100
make drift-check APP=registry KUBE_CONTEXT=kubernetes-admin@kubernetes
```

성공: Pod Running(노드 `khplanew01`), PVC Bound, drift-check 종료 코드 `0`.

## 멈추고 사람에게 묻는 조건

- `registry-check` 실패(노드·PV·Traefik)
- A-3 이후에도 Secret이 없다는 오류
- Pod 재시작 반복(폴더 권한 1000:1000 확인 필요), PVC Pending
- 기존 `/appdata/registry`에 내용이 있음, 다른 Worker로 옮겨야 함
- containerd 재시작이 필요한 경우(노드 영향, 사람만)
