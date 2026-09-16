# 07. 운영과 문제 해결

[가이드 홈](README.md) · 이전: [접속 검증](06-verification.md)

## 1. 이후 업데이트 — CP1

작업 전 현재 커밋·이미지·chart 버전과 DB/파일 백업의 복구 가능 여부를 기록합니다.
checkout 루트에서 로컬 변경과 브랜치를 확인합니다.

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

변경이 있으면 먼저 보존·정리하고, 배포 브랜치가 맞을 때 `git pull --ff-only`를 실행합니다.
새 커밋의 변경 내용에 따라 아래 작업을 선택합니다.

| 변경 | 반영 방법 |
| --- | --- |
| 문서 | 클러스터 적용 불필요 |
| 앱 코드·DAG | 이미지 빌드·반입 → 고유 tag/digest 변경 → 앱별 검사·배포 |
| 앱 manifest·같은 버전의 chart 설정 | 앱별 검사·배포 → 06장 검증 |
| env | 실제 입력 검사 → 해당 Secret 갱신 → 앱별 재시작/Job 재실행 → 기능 확인 |
| TLS | [TLS 절차](../../../keycloak/TLS.md)로 실제 namespace의 Secret 갱신 → backend·VIP·DNS 검증 |
| Portal DB schema | 백업·호환성 확인 → 같은 API 이미지의 migration → 앱 배포 |
| chart/Kubernetes/CNI 버전 | 호환성·업그레이드·복구 절차를 별도 검증 후 수행 |

`up`을 반복해도 기존 Secret을 무조건 교체하지 않는 앱이 있습니다. 예를 들어 Keycloak 도구는
기존 Secret과 파일이 다르면 중단하므로 명시적인 설정 갱신이 먼저 필요합니다.
같은 manifest를 재적용하는 것만으로 Secret을 env로 읽는 Pod가 재시작된다고 가정하지 않습니다.

## 2. 실패했을 때 먼저 읽는 정보

CP1에서 대상 context와 namespace를 선택하고 Pod 이름을 조회 결과에서 입력합니다.

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

재시작 전 로그는 해당 컨테이너를 선택해 `logs ... -c 컨테이너이름 --previous --tail=100`으로 확인합니다.
이전 실행이 없으면 로그가 없는 것이 정상입니다. describe·events·로그에도 앱이 출력한 비밀값이 있을 수 있으므로
공유 전 필요한 부분만 추려 마스킹합니다. 진단 순서는 [공식 Pod 디버깅 안내](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)를 참고합니다.

| 증상 | 먼저 확인할 것 | 다음 조치 |
| --- | --- | --- |
| kubectl timeout / Forbidden | API VIP·인증서·context / 계정 권한 | 네트워크 또는 클러스터 관리자 확인 |
| Node NotReady | 해당 노드 런타임·kubelet·CNI·디스크·시간 | 노드 서비스 로그 확인, init/reset으로 우회하지 않음 |
| Pending | describe Events, 자원·taint·nodeSelector·PVC | 필요한 자원·스토리지·배치 입력 수정 |
| ImagePullBackOff | 이미지명·tag·mirror·CA·imagePullSecret | 실제 노드 런타임의 이미지 접근 확인 |
| CrashLoopBackOff | 이전 로그·종료 코드·env·DB 연결 | 원인 입력/코드 수정 후 앱별 재배포 |
| PVC Pending | StorageClass·정적 PV·노드 affinity | 앱의 저장소 요구와 공급 구성을 맞춤 |
| TLS 오류 | SAN·만료·체인·CA 신뢰·앱 namespace의 Secret | TLS 절차로 수정 후 실제 경로 검사 |
| 404 / 503 | Host·경로·IngressClass·namespace 감시 / Pod·Service endpoint | 실패한 라우팅·준비 상태부터 수정 |
| 로그인 반복·callback 실패 | 공개 issuer·redirect URI·client secret·시간·프록시 HTTPS 전달 | Portal·Keycloak 입력 정합성 확인 |

조회 후 원인을 해결하고 실패한 단계부터 다시 검사합니다. 데이터 삭제나 namespace 재생성을 기본 해결책으로 삼지 않습니다.

## 3. Worker 추가

[Worker 추가 안내](../../ingress/ADD_WORKER.md)를 따릅니다. 노드 등록, Traefik 배치, LB 활성화 순서입니다.
일반 업무 Worker와 APP VIP backend Worker를 구별하고, 기존 backend를 목록에서 빠뜨리지 않습니다.
새 Worker의 직접 HTTPS 접속이 성공한 뒤 LB에서 활성화하고 기존 경로도 다시 확인합니다.

## 4. 백업·복구와 되돌리기

| 대상 | 보관해야 할 것 | 복구 확인 |
| --- | --- | --- |
| 클러스터 | 설치 기준·설정·접근 관리, 설치 방식에 맞는 etcd 백업 | 인프라 담당자의 별도 복구 환경 |
| 앱 DB | DB 일관성이 있는 백업·DB 버전·필요 credential | 별도 DB 복원 후 로그인·조회 |
| Airflow | DB·Fernet 키·동일 이미지/DAG·설정 | [Airflow 이전·백업](../../../airflow/README.md)의 절차와 시험 실행 |
| 업무 파일·MinIO | 실제 영속 저장소 데이터·연결 설정 | 복원 후 업로드·다운로드 |
| 운영 입력 | env·인증서·키·정확한 이미지와 chart 버전 | 접근 제한된 외부 보관, 유효성 확인 |

같은 Worker 디스크의 다른 폴더만으로는 노드·디스크 장애에 대비할 수 없습니다.
실행 중인 PostgreSQL 디렉터리를 단순 복사하는 방법을 일반 백업으로 사용하지 않습니다.
Keycloak DB·etcd의 환경별 백업 명령과 보관 주기·복구 목표는 담당자가 실제 버전·저장소 기준으로 확정해야 하며,
현재 가이드는 이 항목의 복구 검증 완료를 주장하지 않습니다.

배포 실패 시 변경 전 이미지·설정으로 복귀할 수 있는지 먼저 판단합니다. DB migration이나 chart CRD 변경이 있으면
이미지/Helm revision만 되돌려 데이터 호환성이 회복된다고 가정하지 않습니다.
실패 원인·백업·복구 절차를 확인하고 앱별 재적용 후 06장을 반복합니다.

**운영 인수 기준:** 백업 담당·보관 위치·복구 결과·갱신 담당·미완료 항목이 기록됩니다.
과거의 일회성 빈 DB 재설치 기록은 정기 운영·장애 복구 지침으로 사용하지 않습니다.
