# 03. 새 클러스터 구축

[가이드 홈](README.md) · 이전: [서버 준비](02-servers.md) · 다음: [앱 준비](04-prerequisites.md)

**새 검증 환경의 구축 순서입니다.** 설치 도구·버전·CNI가 확정되지 않아 init/join 명령은 아직 제공하지 않습니다.
기존 클러스터에서는 아래 상태 확인 후 04장으로 이동합니다.

## 구축 순서 — 인프라 담당자

| 순서 | 작업 | 완료 조건 |
| --- | --- | --- |
| 1 | API endpoint·LB·etcd 구성 확정 | backend·상태 검사·인증서 대상 이름/IP 기록 |
| 2 | 새 CP1에 첫 제어면 생성 | API·제어면·etcd 정상 |
| 3 | CNI 설치 | 승인된 버전·CIDR·MTU 적용, Pod 네트워크 정상 |
| 4 | CP2·CP3를 한 대씩 연결 | 각 제어면과 API LB backend 정상 |
| 5 | Worker 2대 연결 | 의도한 노드 모두 등록·Ready |
| 6 | DNS·노드 간 통신·스토리지 검증 | 아래 인수 항목 통과 |

설치 입력에는 이미지 저장소·CRI socket·노드 주소·API endpoint·인증서 SAN·Pod/Service CIDR·DNS domain을 포함합니다.
확정된 도구의 해당 버전 절차로 설치하고 실제 설정·명령을 보관합니다.
관리자 kubeconfig·join 토큰·인증서 키는 Git이나 공용 로그에 넣지 않습니다.

## 상태 확인 — CP1

```bash
kubectl config get-contexts
read -r -p '확인할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get --raw='/readyz'
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get service kube-dns
```

API의 `ok`, 노드의 `Ready`, 상시 실행 시스템 Pod의 준비 상태를 확인합니다. 권한 오류는 서비스 장애와 구별합니다.
CNI 준비 전의 NotReady를 이유로 init을 반복하거나, 이미 등록된 노드에 join을 반복하지 않습니다.

## 인수 항목

담당자가 승인된 진단 이미지와 별도 검증 namespace에서 확인합니다.

- 양쪽 Worker의 Pod에서 `kubernetes.default.svc` 이름 해석 성공.
- 같은 노드·다른 노드의 Pod와 Service 사이 통신 성공.
- 사용할 저장소의 PVC 연결·파일 쓰기/읽기 성공.
- API LB 상태 검사·backend 전환과 etcd 상태 확인. 운영 노드 중지는 포함하지 않습니다.

Worker 등록 후 APP VIP 연결은 Traefik 설치와 직접 HTTPS 검증을 마친 뒤 수행합니다.
**완료 기준:** 설치 기준·원본 버전·실행 명령·인수 결과가 남아 있습니다. Ready만으로 앱 접속까지 검증한 것으로 기록하지 않습니다.
