# Monitoring 갱신·백업·문제 해결

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**실행 위치:** 관리 호스트의 저장소 루트입니다. 새 Bash 터미널에서는 [환경설정](01-install.md#1-서버-설정과-디스크-준비)의 context와 env를 다시 export합니다.

## 갱신·운영

설정을 바꾼 뒤에는 **처음 설치할 때와 같은 env·context**로 실행합니다.
새 Bash 세션에서는 [환경설정](01-install.md#1-서버-설정과-디스크-준비)의 `KUBE_CONTEXT`, `MONITORING_ENV`를 다시 export합니다.

```bash
make monitoring-check
make monitoring-up
```

새 Worker는 정상 가입 후 자동으로 수집 대상에 포함되므로, Worker 추가만으로 이 명령을 반복할 필요는 없습니다.
기존 node-exporter가 호스트 포트 `9100`을 사용한다면 새 DaemonSet과 충돌하므로 기존 공용 모니터링 사용 여부를 먼저 정합니다.

| 변경할 내용 | 처리 방법 |
| --- | --- |
| 같은 chart 버전의 설정 | 위 명령으로 검사 후 재적용. `make env-check APP=monitoring`도 입력·렌더 검사에 사용 가능 |
| chart 버전 | 도구가 다른 버전의 기존 release를 발견하면 중단. CRD 호환성과 공식 upgrade 절차를 먼저 검토 |
| Worker·데이터 경로 | 기존 local PV는 일반 재배포로 위치를 변경할 수 없음. [Worker 데이터 이전](../../shared/docs/infrastructure/operations.md#worker-앱-데이터-경로와-이전) 수행 |
| Grafana 관리자 비밀번호 | Grafana DB 생성 후에는 Secret만 바꿔도 기존 비밀번호가 변경되지 않음. Grafana에서 갱신 |
| 백업 | Grafana DB·대시보드·지표를 별도 디스크에 보관. 같은 노드의 데이터만으로 노드 장애를 복구할 수 없음 |

설치 실패 시 도구는 DB·namespace를 자동 삭제하지 않습니다.
일부만 설치됐다면 Helm release 상태와 CRD·Job·Pod를 확인하고 원인을 해결한 뒤 같은 설정으로 재실행합니다.
기존 데이터를 지키기 위해 PVC·namespace·CRD를 임의 삭제하지 않습니다.

## 문제 해결

관리 서버에서 먼저 상태와 최근 이벤트를 확인합니다.

```bash
helm --kube-context "$KUBE_CONTEXT" -n monitoring list --all
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods,pvc,jobs -o wide
kubectl --context "$KUBE_CONTEXT" -n monitoring get events --sort-by=.lastTimestamp
```

| 증상·메시지 | 확인할 내용 |
| --- | --- |
| `실제 값 필요: NODE_NAME` | env의 `replace-me-node`를 실제 hostname label로 변경 |
| `Helm chart 준비 필요` | [chart 준비](01-install.md#2-고정-chart-준비)의 파일 위치와 `MONITORING_CHART_FILE` 확인 |
| `chart SHA-256 불일치` | 고정 버전 패키지를 다시 준비. 임의 chart로 대체하지 않음 |
| 기존 Operator CRD·다른 chart 버전 | 기존 모니터링·release 확인. CRD를 삭제해 우회하지 않음 |
| `ImagePullBackOff`·`ErrImagePull` | 실패한 이미지의 미러 경로·태그·노드 CA·접근 권한·pull Secret 확인. BusyBox도 포함 |
| `monitoring-storage-prepare-*` 실패 | 아래 Job 로그와 Pod Events 확인. root·hostPath 허용, 디스크 마운트, 파일·심볼릭 링크 점유 확인 |
| 기존 PV 경로·노드·PVC 오류 | env를 기존 저장소 설정과 대조. 기존 PV 폴더가 사라졌으면 마운트·데이터부터 복구 |
| `Pending`·PVC 미결합 | 지정 Worker Ready·taint·자원 여유, PV/PVC 연결 상태 확인 |
| Grafana 데이터 폴더 권한 오류 | 기존 폴더의 UID/GID 확인. 자동 생성은 기존 파일 권한을 변경하지 않음 |
| 화면 접속 실패 | DNS/VIP·443 경로, 공용 Traefik·인증서·`INGRESS_HOST` 확인 |
| 새 Worker 지표 없음 | 해당 노드의 node-exporter Pod, 미러 pull, `9100` 통신과 Prometheus target 확인 |

폴더 준비 Job이 실패했다면 **출력된 실제 Job 이름**으로 확인합니다.

```bash
read -r -p '실패한 준비 Job 이름: ' MONITORING_JOB
kubectl --context "$KUBE_CONTEXT" -n monitoring describe job "$MONITORING_JOB"
kubectl --context "$KUBE_CONTEXT" -n monitoring get pods -l "job-name=$MONITORING_JOB"
kubectl --context "$KUBE_CONTEXT" -n monitoring logs "job/$MONITORING_JOB"
```
