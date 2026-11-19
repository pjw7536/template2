# Registry 배포 런북

공통 규칙은 [00-common.md](00-common.md)를 먼저 따릅니다. 명령은 관리 호스트 저장소 루트에서 실행합니다.

## 한눈에 보기

| 항목 | 값 |
| --- | --- |
| namespace | `registry` (Deployment `registry`, Secret `registry-htpasswd`) |
| 실행 Worker | `khplanew01`(관리 호스트와 같은 서버), 데이터 `/appdata/registry` |
| 주소 | `http://registry.etch.samsungds.net` (HTTP, TLS 없음). 경로: DNS → APP VIP `10.172.26.150:80` → 공용 Traefik hostPort 80 → Zot |
| 배포 명령 | `make registry-check` → `make registry-up` (성공 시 배포 기록 자동) |
| 완료 기준 | PVC `Bound`, Pod `Running`, 경로 확인에서 Zot 응답, 사람이 빌드 host push·다른 노드 pull 확인 |
| 먼저 필요한 것 | 공용 Traefik, DNS, APP VIP 80 전달, 저장 폴더, push 계정 Secret |

## 사람이 해야 하는 일

- [사람] DNS `registry.etch.samsungds.net` → APP VIP `10.172.26.150`
- [사람] 인프라 담당자에게 APP VIP `:80` → Traefik backend 80 포트 전달 요청(기록상 미확인)
- [사람] khplanew01에서 `sudo install -d -o 1000 -g 1000 -m 0750 /appdata/registry`
- [사람] 신규 registry는 `deploy/registry/env/push-initial.env`로 bcrypt Secret 생성. 기존 registry는 사용 중인 push 계정 유지
- [사람] 모든 노드와 빌드 host의 containerd HTTP 허용(sudo, 설치 7절 (사람용 `deploy/registry/docs/01-install.md#7-노드와-빌드-host의-http-허용`))
- [사람] 빌드 host push·다른 노드 pull 검증과 시험 이미지 삭제(설치 8절 (사람용 `deploy/registry/docs/01-install.md#8-pushpull-검증`))

## 입력

| 이름 | 의미 | 기본값 |
| --- | --- | --- |
| `REGISTRY_ENV` | Registry env 경로 | `deploy/registry/env/k8s.env` |
| env 키 | `NODE_NAME=khplanew01`, `REGISTRY_IMAGE`, `IMAGE_PULL_SECRET`(비움), `REGISTRY_HOST=registry.etch.samsungds.net`, `DATA_HOST_PATH=/appdata/registry`, `STORAGE_SIZE` | |
| Traefik 노드 IP | 6단계에서 조회 | 저장소 기본 배치는 `khplane01w09`(`10.172.40.87`) |

## A. 최초 설치

1. [사람] DNS 등록, APP VIP 80 전달 요청, `/appdata/registry` 폴더 준비를 사용자에게 확인합니다.
2. [조회] DNS·폴더 확인
   ```bash
   getent hosts registry.etch.samsungds.net
   ls -ld /appdata/registry
   ```
   성공: `10.172.26.150`이 조회되고, 폴더 소유자가 `1000 1000`. 다르면 멈추고 [사람]에게 요청합니다.
3. [검사] 배포 전 검사
   ```bash
   make registry-check KUBE_CONTEXT="<context>"
   ```
   성공: `registry 입력·노드·저장소·라우팅 검사 통과. 클러스터를 변경하지 않았습니다.` 신규 설치면 PV·namespace 생성 예정 안내가 함께 나옵니다.
4. [변경] namespace 생성(승인 필요)
   ```bash
   make registry-up KUBE_CONTEXT="<context>"
   ```
   **최초 실행은 의도적으로 실패 종료합니다.** `registry namespace를 만들었습니다. Secret registry-htpasswd을 만든 뒤 up을 다시 실행하세요.`가 나오면 정상이며 다음 단계로 갑니다. 다른 오류면 멈춥니다.
5. [사람] 설치 4절 (사람용 `deploy/registry/docs/01-install.md#4-namespace와-push-계정-준비`)에 따라 push 계정 Secret 등록과 이름 확인을 요청합니다. 완료 답을 받은 뒤 배포합니다.
6. [변경] 배포(승인 필요). Traefik 감시 범위가 바뀌어 Traefik이 재기동됩니다.
   ```bash
   make registry-up KUBE_CONTEXT="<context>"
   ```
   성공: `registry 배포 완료: http://registry.etch.samsungds.net/v2/`와 `배포 기록 저장: registry/deploy-record-registry`.
7. [조회] Traefik 업로드 시간 설정 반영 여부
   ```bash
   kubectl --context "<context>" -n etch-sso get deployment traefik -o jsonpath='{.spec.template.spec.containers[?(@.name=="traefik")].args}{"\n"}' | grep -c 'readTimeout=600s'
   ```
   결과가 `1`이면 8단계로 갑니다. `0`이면 다음 두 명령을 실행합니다.
   - [검사] `make ingress-check KUBE_CONTEXT="<context>"` → 성공: `공용 Ingress 원본·배치 검사 통과`
   - [변경] `make ingress-up KUBE_CONTEXT="<context>"`(승인 필요, Traefik 재기동) → 성공: `공용 Ingress 준비 완료`. 다시 조회해 `1`인지 확인합니다.
8. [조회] 접속 경로 확인. 먼저 Traefik 노드 IP를 확인하고 두 번째 명령의 `<Traefik 노드 IP>`에 넣습니다.
   ```bash
   kubectl --context "<context>" -n etch-sso get pods -l app.kubernetes.io/name=traefik -o wide
   ```
   ```bash
   curl -sS -o /dev/null -D - -H 'Host: registry.etch.samsungds.net' http://<Traefik 노드 IP>/v2/ | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
   curl -sS -o /dev/null -D - http://registry.etch.samsungds.net/v2/ | grep -i -E '^HTTP/|^docker-distribution-api-version|^www-authenticate'
   ```
   성공: 두 요청 모두 `200`이거나, `401`이면서 `realm="registry"`가 보임.

   | 결과 | 원인과 행동 |
   | --- | --- |
   | 첫 요청 `404`, `realm="registry"` 없음 | Traefik이 `registry` namespace를 감시하지 않음. 6단계 결과를 보고하고 멈춤 |
   | 첫 요청 성공, 두 번째 연결 실패·timeout | DNS 또는 APP VIP 80 전달 미설정. [사람]에게 인프라 확인 요청 |
   | 첫 요청 연결 거부 | Traefik hostPort 80 미기동. 멈추고 보고 |
9. [조회] [C. 배포 후 확인](#c-배포-후-확인)을 실행합니다.
10. [사람] 모든 노드·빌드 host의 containerd HTTP 허용과 push·pull 검증, 시험 이미지 삭제를 요청합니다. 실패 문구별 원인은 설치 8절 (사람용 `deploy/registry/docs/01-install.md#8-pushpull-검증`)에 있습니다.
11. 운영 기록: push·pull이 확인되면 [pending](../../../../deploy/shared/docs/infrastructure/pending.md)의 registry 관련 행(DNS 등록, APP VIP HTTP(80) 전달, 사내 이미지 저장소 배포)을 사용자 확인 결과에 맞게 정리합니다.

## B. 업데이트

| 변경 | 실행 |
| --- | --- |
| env·이미지 태그 | A-3 → A-6 → A-8 → C. `registry-up`은 매번 재시작함 |
| 공용 Traefik 설정 변경 | A-7 |
| push 계정 교체 | 멈추고 사람에게 묻기(빌드 host 재로그인 필요, 운영 (사람용 `deploy/registry/docs/02-operations.md`)) |
| 이미지 태그 삭제 | 사람만. 되돌릴 수 없음 |

## C. 배포 후 확인

모두 [조회]입니다.

```bash
kubectl --context "<context>" -n registry get pods,pvc,ingress -o wide
kubectl --context "<context>" -n registry logs deployment/registry --tail=50
```

성공: Pod Running(노드 `khplanew01`), PVC Bound, Ingress host `registry.etch.samsungds.net`, 공통 마무리의 JSON 판정 `0`.

## 멈추고 사람에게 묻는 조건

- `registry-check` 실패(노드 Ready·taint, 기존 PV 경로·노드 불일치, PV Released)
- A-4 이후에도 Secret이 없다는 오류
- Pod 재시작 반복(폴더 권한 1000:1000), PVC Pending, 이미지 pull 실패
- 기존 `/appdata/registry`에 내용이 있음, 다른 Worker로 옮겨야 함
- A-8 경로 확인 실패
- containerd 설정 변경·재시작이 필요한 경우(노드 영향, 사람만)
