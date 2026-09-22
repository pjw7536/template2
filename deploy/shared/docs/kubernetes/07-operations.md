# 07. 운영과 문제 해결

[가이드 홈](README.md) · 이전: [검증](06-verification.md)

## 업데이트 — CP1

현재 커밋·이미지·chart와 DB/파일 백업을 기록한 뒤 checkout 루트에서 확인합니다.

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

로컬 변경을 보존하고 배포 브랜치가 맞으면 `git pull --ff-only`를 실행합니다.

| 변경 | 반영 순서 |
| --- | --- |
| 문서 | 클러스터 적용 불필요 |
| 앱 코드·DAG | 이미지 빌드·반입 → 고유 tag/digest → 앱별 검사·배포 |
| manifest·chart 설정 | 앱별 검사·배포 |
| env | 실제 입력 검사 → Secret 갱신 → 필요한 재시작·Job |
| TLS | [TLS 절차](../../../keycloak/TLS.md)로 해당 namespace의 Secret 갱신 |
| Portal DB schema | 백업·호환성 확인 → 같은 API 이미지로 migration → 배포 |
| chart·Kubernetes·CNI 버전 | 별도 호환성·업그레이드·복구 검증 후 수행 |

적용 후 [06장](06-verification.md)을 반복합니다.
Keycloak은 기존 Secret과 입력이 다르면 중단하므로 명시적인 갱신이 먼저 필요합니다.
Secret 변경만으로 이를 env로 읽는 Pod가 재시작되지는 않습니다.

## 장애 조회 — CP1

```bash
kubectl config get-contexts
read -r -p '확인할 Kubernetes context: ' KUBE_CONTEXT
read -r -p '앱 namespace: ' APP_NAMESPACE
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get events --sort-by=.metadata.creationTimestamp
read -r -p '문제 Pod 이름: ' APP_POD
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" describe pod "$APP_POD"
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" logs "$APP_POD" --all-containers --tail=100
```

재시작 전 로그는 `logs ... -c 컨테이너이름 --previous --tail=100`으로 확인합니다.
공유 전 describe·events·로그의 비밀값을 마스킹합니다.

| 증상 | 먼저 확인할 것 |
| --- | --- |
| kubectl timeout / Forbidden | API VIP·인증서·context / 계정 권한 |
| Node NotReady | 런타임·kubelet·CNI·디스크·시간, 해당 서비스 로그 |
| Pending / PVC Pending | Events·자원·taint·nodeSelector·StorageClass·PV affinity |
| ImagePullBackOff | 이미지 tag·mirror·CA·imagePullSecret·노드 이미지 접근 |
| CrashLoopBackOff | 이전 로그·종료 코드·env·DB 연결 |
| TLS 오류 | SAN·만료·체인·CA·앱 namespace의 TLS Secret |
| 404 / 503 | Host·경로·IngressClass·namespace 감시 / Pod·Service endpoint |
| 로그인 반복·callback 실패 | issuer·redirect URI·client secret·시간·HTTPS 전달 |

원인을 해결한 뒤 실패한 단계부터 재검사합니다. init/reset·PVC 삭제·namespace 재생성을 기본 복구 방법으로 삼지 않습니다.

## Worker 추가

[Worker 추가 안내](../../ingress/ADD_WORKER.md)의 노드 등록 → Traefik 배치 → 직접 HTTPS 확인 → LB 활성화 순서로 진행합니다.
APP VIP backend 전체 목록에서 기존 Worker를 빠뜨리지 않고 기존 경로도 다시 확인합니다.

## 백업·복구

| 대상 | 보관·복구 확인 |
| --- | --- |
| 클러스터 | 설치 기준·설정·etcd 백업 → 별도 환경 복구 |
| 앱 DB | 일관성 있는 DB 백업·버전·credential → 별도 DB 복원·로그인·조회 |
| Airflow | DB·Fernet 키·이미지/DAG·설정 → [이전·백업 절차](../../../airflow/README.md)와 시험 실행 |
| 업무 파일·MinIO | 영속 데이터·연결 설정 → 복원 후 업로드·다운로드 |
| 운영 입력 | env·인증서·키·이미지/chart 버전 → 접근 제한된 외부 보관 |

같은 Worker 디스크의 다른 폴더는 디스크 장애에 대비한 백업이 아닙니다.
실행 중 PostgreSQL 디렉터리를 단순 복사하지 않습니다. DB migration·CRD 변경은 이미지나 Helm revision만 되돌려 복구되지 않을 수 있습니다.

**운영 인수 기준:** 백업 담당·보관 위치·주기·복구 목표·복구 시험 결과를 기록합니다.
Keycloak DB·etcd의 환경별 백업 명령과 복구 검증은 아직 확정되지 않았습니다.
