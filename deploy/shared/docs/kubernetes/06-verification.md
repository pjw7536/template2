# 06. 접속과 기능 검증

[가이드 홈](README.md) · 이전: [앱 배포](05-applications.md) · 다음: [운영](07-operations.md)

배포 명령이 끝나도 실제 사용자 경로를 확인해야 합니다. 아래 순서를 따르면 실패한 구간을 좁힐 수 있습니다.
앱을 배포하지 않았다면 해당 검사를 `미배포`로 기록하며 실패로 해석하지 않습니다.

## 1. 노드·Pod·스토리지 — CP1

`KUBE_CONTEXT`를 선택한 터미널에서 실행합니다. namespace는 실제 배포 설정에서 확인합니다.

```bash
kubectl --context "$KUBE_CONTEXT" get nodes -o wide
read -r -p '확인할 앱 namespace: ' APP_NAMESPACE
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get deployment,statefulset,daemonset
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get pods -o wide
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get jobs
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get pvc
kubectl --context "$KUBE_CONTEXT" -n "$APP_NAMESPACE" get service,ingress,endpointslices
```

**성공 조건:** 원하는 replica 준비, 상시 실행 Pod의 READY 충족, 필요한 PVC의 Bound,
일회성 Job의 완료, Service에 대응하는 준비된 endpoint가 존재합니다.
Job의 Completed는 정상이며 Pod의 Running만으로 READY 충족을 대신하지 않습니다.

## 2. Worker → VIP → DNS — 내 PC 또는 접근 가능한 검증 호스트

APP VIP를 사용하는 앱은 먼저 Worker 각각에 접속한 뒤 VIP와 일반 DNS 경로를 확인합니다.
다음은 1개 경로를 검사하는 양식입니다. 실제 앱의 정상 health 경로를 입력합니다.
Airflow는 `/airflow/health`, Portal은 `/api/v1/health/`를 사용합니다.

```bash
read -r -p '앱의 인증서 도메인: ' APP_HOST
read -r -p 'health 경로(/로 시작): ' APP_HEALTH_PATH
read -r -p '확인할 Worker 또는 VIP IP: ' TARGET_IP
read -r -p '신뢰할 CA PEM 파일 절대 경로: ' CA_FILE
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" --resolve "$APP_HOST:443:$TARGET_IP" \
  "https://$APP_HOST$APP_HEALTH_PATH"
```

같은 도메인·경로를 유지하고 TARGET_IP를 각 backend, APP VIP 순서로 바꿔 실행합니다.
OS에서 이미 CA를 신뢰하면 `--cacert`를 생략할 수 있습니다. 인증서 확인을 건너뛰는 `-k`는 사용하지 않습니다.
`--resolve`는 DNS를 우회하면서 도메인·TLS를 유지하는 검사입니다. 최종 DNS도 별도로 확인합니다.

```bash
curl --fail --show-error --connect-timeout 5 --max-time 20 \
  --cacert "$CA_FILE" "https://$APP_HOST$APP_HEALTH_PATH"
```

**성공 조건:** 각 경로에서 인증서 검증과 앱 health 내용이 정상입니다.
Airflow는 HTTP 200 외에 metadatabase·scheduler의 healthy도 확인합니다.
Keycloak은 [VIP 문서](../../ingress/VIP.md)의 도메인 검사와 브라우저 로그인을 수행합니다.
루트 경로를 서비스하지 않는 앱에서 `/`의 404만 보고 장애로 판단하지 않습니다.

## 3. 앱별 실제 기능 — 내 PC

| 앱 | 확인할 시나리오 |
| --- | --- |
| Keycloak | HTTPS → 사내 OIDC 로그인 → realm·사용자 claim 확인 |
| Portal | 화면 → 로그인 callback → API 사용 → 로그아웃, 시험 파일 업로드·다운로드 |
| Airflow | UI 로그인 → health 내용 → Portal 연동 사용 시 시험 DAG 트리거·결과 확인 |
| Monitoring | Grafana 로그인 → 노드 지표, Prometheus target 상태 |
| Headlamp | 토큰 로그인 → 노드·Pod·허용된 로그 조회 |
| FTP | 선택 노드에 passive 접속 → 시험 파일 업로드·다운로드 → 해당 노드 저장 위치 확인 |

시험 데이터는 기존 업무 데이터와 구분하고 앱의 정상 삭제 방법으로 정리합니다.

## 4. 결과 기록

| 항목 | 기록 내용 |
| --- | --- |
| 대상 | 수행일·담당자·context·namespace·커밋·이미지 tag/digest·chart 버전 |
| 정적 검사 | 원본·env·렌더 검사 결과 |
| 클러스터 | 노드·rollout·Job·PVC·endpoint 결과 |
| 사용자 경로 | Worker별·VIP·DNS·TLS·로그인·선택 업무 결과 |
| 미완료 | 미배포 / 실패 / 환경 접근 불가 / 확인 대기를 구분하고 다음 조치 기록 |

실제 credential과 로그인 token은 결과표에 넣지 않습니다.
**완료 기준:** 선택한 앱의 필요한 행에 실제 결과가 있고, 검증하지 않은 항목을 성공으로 표시하지 않습니다.
