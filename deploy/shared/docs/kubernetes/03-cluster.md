# 03. 클러스터 구축

[가이드 홈](README.md) · 이전: [서버 준비](02-servers.md) · 다음: [배포 준비](04-prerequisites.md)

**새 검증 환경의 구축 순서이며 현재 운영 클러스터에서 실행하는 재설치 절차가 아닙니다.**
설치 도구·Kubernetes 버전·CNI가 미확정이므로 init/join·CNI 설치 명령은 아직 제공하지 않습니다.
확인된 설치 도구의 버전별 절차를 아래 순서에 채우고 검증해야 빈 서버 재현 안내가 완성됩니다.
기존 클러스터에서는 4절의 조회를 수행한 뒤 04장으로 이동합니다.

## 1. API 진입점 — 인프라 담당자

Control Plane 3대가 공유할 API endpoint, LB backend, 상태 검사와 인증서의 대상 이름/IP를 확정합니다.
APP VIP와 혼동하지 않도록 관리용/사용자용을 기준표에 따로 적습니다.
노드와 배포 계정에서 API endpoint로 연결할 수 있어야 합니다.

kubeadm 방식으로 확인되면 [공식 HA 구축 절차](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/)를
확인된 버전으로 선택합니다. 해당 절차는 API LB 주소와 `controlPlaneEndpoint`를 일치시키도록 안내합니다.
etcd가 Control Plane에 함께 있는지, 외부 etcd인지도 실제 기준과 일치시킵니다.

**완료 기준:** endpoint·backend·etcd 방식·인증서 요구사항이 기록되고 네트워크 담당자가 연결 조건을 확인합니다.
API가 아직 시작되지 않은 상태의 연결 실패와 LB 경로 불통을 구분합니다.

## 2. 첫 Control Plane과 CNI — 새 CP1

인프라 담당자가 다음 내용을 포함한 설치 설정과 실제 명령을 확정합니다.

| 설치 입력 | 확인할 조건 |
| --- | --- |
| Kubernetes 버전·이미지 저장소 | 반입 이미지와 설치 도구의 버전 일치 |
| 노드 advertise address·CRI socket | 새 CP1의 인터페이스·런타임과 일치 |
| 공통 API endpoint·인증서 SAN | API VIP와 클라이언트 접속 이름 포함 |
| Pod CIDR·Service CIDR·DNS domain | 사내 네트워크와 충돌하지 않으며 CNI 설정과 일치 |
| CNI 버전·설치 원본·설정 | 승인된 반입물, 필요한 노드 통신·MTU 확인 |

확정된 도구로 첫 제어면을 생성하고, 배포 계정에 필요한 kubeconfig를 안전하게 전달한 다음 CNI를 설치합니다.
관리자 kubeconfig와 join에 필요한 토큰·인증서 키는 문서·Git·공용 로그에 기록하지 않습니다.
네트워크 플러그인이 준비되기 전의 NotReady/CoreDNS 대기를 이유로 init을 반복하지 않습니다.

**완료 기준:** API 조회 성공, 첫 제어면·etcd 정상, CNI 설치 완료. 실패하면 설치 도구 로그와 런타임·CNI를 먼저 확인합니다.

## 3. 추가 Control Plane·Worker — 각 새 노드

관리자가 발급한 절차로 추가 Control Plane 2대를 한 대씩 연결하고 각각 정상 동작을 확인합니다.
이후 Worker 2대를 연결합니다. Control Plane용과 Worker용 join 입력을 구별합니다.
만료된 입력은 관리자가 재발급하며 이미 등록된 노드에서 join을 반복하지 않습니다.

**완료 기준:** API LB의 각 제어면 backend가 정상이고 의도한 노드가 모두 등록됩니다.
Worker 등록과 APP VIP backend 등록은 별개입니다. 후자는 앱 진입점 설치·검증 후 수행합니다.

## 4. 구축 인수 — CP1·인프라 담당자

조회 대상은 매 터미널에서 지정합니다.

```bash
kubectl config get-contexts
read -r -p '확인할 Kubernetes context: ' KUBE_CONTEXT
export KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get --raw='/readyz'
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n kube-system get service kube-dns
```

일반적인 성공 결과는 API의 `ok`, 대상 노드의 `Ready`, 상시 실행 시스템 Pod의 준비 완료입니다.
권한 오류는 서비스 장애와 구별합니다. DNS Service 조회는 실제 DNS 해석 성공까지 보장하지 않습니다.

인프라 담당자는 승인된 진단 이미지와 별도 검증 namespace에서 다음 결과도 기록합니다.
진단 이미지·실행 명령은 CNI와 반입 기준 확정 시 이 절에 추가합니다.

- 양쪽 Worker의 진단 Pod에서 `kubernetes.default.svc` 이름 해석 성공.
- 같은 노드·다른 노드의 검증 Pod와 검증 Service 사이의 의도한 통신 성공.
- 실제로 사용할 저장소에 PVC 연결·파일 쓰기/읽기 성공.
- API LB 상태 검사·backend 전환 검증 및 etcd 상태 확인. 운영 노드 중지는 이 인수 절차에 포함하지 않음.

**이 장의 완료 기준:** 기준표·설치 명령·원본 버전·검증 결과가 모두 남아 있고 위 검사를 통과합니다.
단순히 노드가 Ready인 것만으로 앱 저장소·외부 접속까지 검증됐다고 표시하지 않습니다.
