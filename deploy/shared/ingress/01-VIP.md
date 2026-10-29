# APP VIP와 앱 HTTPS 연결

[공용 Ingress 안내](README.md) · [Traefik 셋업](../docs/kubernetes/02-traefik.md) · [Worker 확장](02-ADD_WORKER.md)

APP VIP는 외부 요청을 Traefik이 실행되는 Worker로 전달하는 네트워크 진입점입니다.
앱과 DB의 실행 Worker는 각 앱의 배포 입력에서 별도로 정합니다.
VIP에 Worker를 추가해도 앱·DB가 자동 복제되지는 않습니다.

## 1. 실제 대상과 연결 방식 확인

인프라 담당자가 설정한 VIP·DNS·Backend IP·포트와 Kubernetes 노드 목록을 대조합니다.
TCP로 Worker의 443에 전달하고 TLS는 Traefik에서 종료하는 구성을 기준으로 합니다.
TLS offloading·PROXY protocol 등 다른 방식을 사용한다면 LB와 Traefik 설정을 함께 확인합니다.

명령은 배포 호스트의 저장소 루트에서 실행합니다.

```bash
read -r -p '대상 Kubernetes context: ' KUBE_CONTEXT
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
kubectl --context "$KUBE_CONTEXT" -n etch-sso get pods -o wide
read -r -p '유지할 전체 VIP Backend Worker IP 목록(쉼표 구분): ' VIP_BACKENDS
```

Backend IP는 실제 Node의 InternalIP와 일치해야 합니다.
각 Worker의 80/443 포트·이미지 접근·CNI 연결을 확인하며, 상세 사전 조건은 [Worker 확장](02-ADD_WORKER.md)을 따릅니다.

## 2. 인증서와 공용 진입점 준비

사이트 인증서·개인키·CA를 [인증서 안내](../certs/README.md)에 따라 검증하고 공용 TLS 저장소에 등록합니다.
그다음 선택한 context와 전체 Backend 목록으로 검사·적용합니다.

```bash
make ingress-check KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
make ingress-up KUBE_CONTEXT="$KUBE_CONTEXT" VIP_BACKENDS="$VIP_BACKENDS"
```

검사는 노드·원본·선언된 포트 충돌을 확인합니다. 적용은 공용 진입점을 갱신하며 Keycloak·Airflow·DB를 재배포하지 않습니다.
Backend를 추가할 때는 유지할 기존 IP도 모두 포함합니다. 운영 중 배치를 바꾼다면 [백업·복구 포함 확장 절차](02-ADD_WORKER.md)를 따릅니다.

## 3. 필요한 앱 배포

Keycloak은 [설치·로그인 설정](../../keycloak/README.md), Airflow는 [검사·배포·접속](../../airflow/04_SETUP_FLOW.md)을 따릅니다.
Portal·Monitoring·Headlamp·MinIO 등은 [앱별 배포 순서](../docs/kubernetes/05-applications.md)에서 해당 앱 문서로 이동합니다.
앱별 Ingress host·path와 공용 Traefik의 namespace 감시를 확인합니다.

## 4. Backend와 VIP 접속 검증

각 Worker에 직접 연결했을 때와 VIP를 통해 연결했을 때 같은 사이트 인증서와 앱 응답을 받아야 합니다.
[접속·기능 검증](../docs/kubernetes/06-verification.md)에 따라 실제 도메인·CA를 사용해 HTTPS와 로그인을 확인합니다.
Pod Ready·Ingress 등록·파일 검사만으로 외부 접속 성공을 판단하지 않습니다.
