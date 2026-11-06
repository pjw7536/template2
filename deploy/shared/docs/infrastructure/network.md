# 네트워크·VIP·DNS

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

클러스터·업무 네트워크 주소와 연결 관계의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
담당자는 미확인입니다. 접속 경로의 확인 범위와 남은 확인은 아래 항목을 따릅니다.

## VIP·DNS·접속 경로

| 용도 | 주소·연결 | 근거·확인 상태 |
| --- | --- | --- |
| Kubernetes API VIP | `10.172.26.148:6443` | API 접속점. 실제 kubeconfig·가입 endpoint·LB backend 확인 필요 |
| 업무 서비스 APP VIP | `10.172.26.150:443` | 사용자 확인: 인프라팀 발급, SSH 접근 대상 아님. 현재 LB·HTTPS 응답 확인 필요 |
| 업무 DNS → APP VIP | `etch.samsungds.net` → `10.172.26.150` | 사용자 확인: DNS 연결. 현재 DNS 응답·인증서 확인 필요 |
| SSO DNS | `etch-sso.samsungds.net` → 업무 DNS와 다른 IP, 구체 값 미확인 | 사용자 확인: 업무 도메인과 IP가 다름. 실제 DNS 응답·연결 IP·LB backend·TLS 종료 위치 확인 필요 |
| 업무 HTTPS 인증서 신청 | CN: `etch.samsungds.net`, SAN 신청값: `etch.samsungds.net`, `10.172.26.150` | 사용자 확인: 신청 범위. `stg.etch.samsungds.net`은 신청값에 없음. 실제 발급 여부·SAN의 DNS/IP 유형·유효기간·서버 적용은 미확인. 파일·등록 절차는 [인증서 관리](../../certs/README.md) 참조 |
| APP VIP backend 1 | `10.172.40.117:443` → `khplanew01` | 사용자 확인: LB backend·노드 대응. 현재 backend·Traefik 응답은 재조회 |
| APP VIP backend 2 | `10.172.40.87:443` → `khplane01w09` | 사용자 확인: LB backend·노드 대응. 현재 backend·Traefik 응답은 재조회 |
| HTTPS 연결 | APP VIP → Worker hostPort 443 → 공용 Traefik → 앱 Service | [VIP 절차](../../ingress/01-VIP.md)의 목표 구성. TLS는 Traefik에서 종료하며 실제 LB 전달 방식·PROXY protocol 사용 여부 확인 필요 |

Keycloak DNS는 업무 도메인과 다른 IP에 연결된다는 사용자 확인이 있습니다.
구체 연결 IP·APP VIP와의 관계·Worker 직결 여부·TLS 종료 위치는 별도 조회가 필요합니다.
별도 검증 클러스터의 노드·관리 endpoint에는 운영 IP를 재사용하지 않습니다.
아래 동일 클러스터 내 테스트·운영 앱의 APP VIP 공유 계획과는 구분합니다.

### DNS 명명과 향후 구역 위임

사용자는 향후 DNS 구역 위임을 받을 수 있도록 신규 서비스 주소를 `etch.samsungds.net` 아래에
모으는 계층형 명명을 선택했습니다. 명명 원칙은 사용자 확인이며, 구역 위임은 향후 선택 사항입니다.

| 대상 | 명명 원칙·관리 범위 | 확인 상태·남은 확인 |
| --- | --- | --- |
| 향후 위임할 구역 | `etch.samsungds.net` | 위임을 고려한 명명 선택은 사용자 확인. 사내 허용 여부·관리 권한·실제 위임은 미확인 |
| 운영 기본 주소 | `etch.samsungds.net` | 기존 업무 DNS·APP VIP 연결 유지. 위임 시에도 구역 최상위의 업무 주소 레코드를 보존해야 함 |
| 서비스 운영 | `<service>.etch.samsungds.net` | SAN 신청안과 서비스별 전환안의 주소 규칙. `etch-<service>.samsungds.net`으로 일괄 변경하지 않음 |
| 테스트 구역·기본 주소 | `stg.etch.samsungds.net` | Portal 테스트 주소이자 향후 테스트 구역 재위임 후보. 실제 재위임 여부·관리 권한·권한 DNS 서버는 미확인 |
| 서비스 테스트 | `<service>.stg.etch.samsungds.net` | 모든 서비스 테스트 주소를 `stg.etch.samsungds.net` 아래에 배치 |
| 기존 SSO 예외 | `etch-sso.samsungds.net` | 기존 주소 유지. `etch.samsungds.net` 하위가 아니므로 해당 구역 위임 범위에 포함되지 않음 |

현재는 필요한 레코드를 사내 DNS 관리 절차로 신청합니다. 향후 위임하려면 사내 DNS팀과
상위 구역의 NS 위임, 관리할 권한 DNS 서버·접속 가능 경로·가용성·담당자를 별도로 정해야 합니다.
`etch.samsungds.net` 구역을 위임받으면 `stg.etch.samsungds.net`과 그 아래 주소도 관리할 수 있습니다.
테스트 관리자를 따로 둘 때는 `stg.etch.samsungds.net` 구역의 NS 재위임을 별도로 구성할 수 있습니다.
현재 DNS·NS 레코드나 서버 구성을 변경한 상태가 아니며 DNS 운영 도구도 선택하지 않았습니다.
DNS 위임과 서버 인증서 발급은 별도입니다. 와일드카드 미지원 조건과 주소별 SAN 등록 원칙은 유지합니다.

### 앱별 도메인 전환을 위한 인증서 추가 신청안

사내 인증서 신청은 와일드카드를 지원하지 않는다는 사용자 확인에 따라 개별 도메인을 SAN에 명시합니다.
CN은 `etch.samsungds.net`이며 운영 기본 도메인도 SAN에 함께 넣습니다.
아래 신청안에는 기존에 요청한 SSO 통합·IP 직접 접속 항목을 함께 유지하며,
기존 신청 범위·실제 발급·DNS·서버 적용 상태와 구분합니다.
재신청을 줄이기 위해 현재 서비스·서비스별 테스트 주소와 향후 용도별 예약 후보까지 포함한 확장안입니다.
전체 신청안은 DNS SAN 151개·IP SAN 1개이며, 사내 발급 시스템의 SAN 개수 제한은 미확인입니다.
사용자가 지정한 plane·spider·board·apc·eqp·datalake·wio·kpi·automation·ax와 관련 업무·데이터 서비스의 예약 후보를 포함합니다.
테스트 주소는 `서비스.stg.etch.samsungds.net` 규칙을 사용하며 Portal 테스트는 `stg.etch.samsungds.net`입니다.
기존 SSO 주소·issuer는 유지합니다. `sso.etch.samsungds.net`과 `sso.stg.etch.samsungds.net`은
향후 사용할 수 있는 예비 SAN으로만 포함하며 SSO 이전·별도 테스트 SSO 배포를 수행한 상태가 아닙니다.
서비스별 주소 용도는 [앱별 도메인 전환안](services.md#앱별-도메인-전환안)에서 관리합니다.
인증서 신청 제출·발급·적용과 신규 DNS 등록은 미확인입니다. 담당자는 미확인입니다.

```text
CN: etch.samsungds.net

Subject Alternative Name (SAN):
  DNS: etch.samsungds.net
  DNS: airflow.etch.samsungds.net
  DNS: s3.etch.samsungds.net
  DNS: minio.etch.samsungds.net
  DNS: grafana.etch.samsungds.net
  DNS: prometheus.etch.samsungds.net
  DNS: alertmanager.etch.samsungds.net
  DNS: headlamp.etch.samsungds.net
  DNS: api.etch.samsungds.net
  DNS: git.etch.samsungds.net
  DNS: registry.etch.samsungds.net
  DNS: ci.etch.samsungds.net
  DNS: docs.etch.samsungds.net
  DNS: status.etch.samsungds.net
  DNS: logs.etch.samsungds.net
  DNS: traces.etch.samsungds.net
  DNS: dev.etch.samsungds.net
  DNS: preview.etch.samsungds.net
  DNS: plane.etch.samsungds.net
  DNS: spider.etch.samsungds.net
  DNS: board.etch.samsungds.net
  DNS: apc.etch.samsungds.net
  DNS: eqp.etch.samsungds.net
  DNS: datalake.etch.samsungds.net
  DNS: dashboard.etch.samsungds.net
  DNS: observer.etch.samsungds.net
  DNS: report.etch.samsungds.net
  DNS: analytics.etch.samsungds.net
  DNS: catalog.etch.samsungds.net
  DNS: pipeline.etch.samsungds.net
  DNS: search.etch.samsungds.net
  DNS: rag.etch.samsungds.net
  DNS: assistant.etch.samsungds.net
  DNS: files.etch.samsungds.net
  DNS: notebook.etch.samsungds.net
  DNS: model.etch.samsungds.net
  DNS: wio.etch.samsungds.net
  DNS: kpi.etch.samsungds.net
  DNS: automation.etch.samsungds.net
  DNS: ax.etch.samsungds.net
  DNS: sso.etch.samsungds.net
  DNS: fdc.etch.samsungds.net
  DNS: esop.etch.samsungds.net
  DNS: sop.etch.samsungds.net
  DNS: defectmap.etch.samsungds.net
  DNS: voc.etch.samsungds.net
  DNS: teamstaff.etch.samsungds.net
  DNS: mail.etch.samsungds.net
  DNS: llm.etch.samsungds.net
  DNS: mcp.etch.samsungds.net
  DNS: oes.etch.samsungds.net
  DNS: ieq.etch.samsungds.net
  DNS: ai.etch.samsungds.net
  DNS: data.etch.samsungds.net
  DNS: cowork.etch.samsungds.net
  DNS: workspace.etch.samsungds.net
  DNS: tasks.etch.samsungds.net
  DNS: projects.etch.samsungds.net
  DNS: workflow.etch.samsungds.net
  DNS: approval.etch.samsungds.net
  DNS: forms.etch.samsungds.net
  DNS: calendar.etch.samsungds.net
  DNS: wiki.etch.samsungds.net
  DNS: knowledge.etch.samsungds.net
  DNS: assets.etch.samsungds.net
  DNS: inventory.etch.samsungds.net
  DNS: quality.etch.samsungds.net
  DNS: yield.etch.samsungds.net
  DNS: process.etch.samsungds.net
  DNS: recipe.etch.samsungds.net
  DNS: metrology.etch.samsungds.net
  DNS: maintenance.etch.samsungds.net
  DNS: alarm.etch.samsungds.net
  DNS: events.etch.samsungds.net
  DNS: audit.etch.samsungds.net
  DNS: store.etch.samsungds.net
  DNS: stg.etch.samsungds.net
  DNS: airflow.stg.etch.samsungds.net
  DNS: s3.stg.etch.samsungds.net
  DNS: minio.stg.etch.samsungds.net
  DNS: grafana.stg.etch.samsungds.net
  DNS: prometheus.stg.etch.samsungds.net
  DNS: alertmanager.stg.etch.samsungds.net
  DNS: headlamp.stg.etch.samsungds.net
  DNS: api.stg.etch.samsungds.net
  DNS: git.stg.etch.samsungds.net
  DNS: registry.stg.etch.samsungds.net
  DNS: ci.stg.etch.samsungds.net
  DNS: docs.stg.etch.samsungds.net
  DNS: status.stg.etch.samsungds.net
  DNS: logs.stg.etch.samsungds.net
  DNS: traces.stg.etch.samsungds.net
  DNS: plane.stg.etch.samsungds.net
  DNS: spider.stg.etch.samsungds.net
  DNS: board.stg.etch.samsungds.net
  DNS: apc.stg.etch.samsungds.net
  DNS: eqp.stg.etch.samsungds.net
  DNS: datalake.stg.etch.samsungds.net
  DNS: dashboard.stg.etch.samsungds.net
  DNS: observer.stg.etch.samsungds.net
  DNS: report.stg.etch.samsungds.net
  DNS: analytics.stg.etch.samsungds.net
  DNS: catalog.stg.etch.samsungds.net
  DNS: pipeline.stg.etch.samsungds.net
  DNS: search.stg.etch.samsungds.net
  DNS: rag.stg.etch.samsungds.net
  DNS: assistant.stg.etch.samsungds.net
  DNS: files.stg.etch.samsungds.net
  DNS: notebook.stg.etch.samsungds.net
  DNS: model.stg.etch.samsungds.net
  DNS: wio.stg.etch.samsungds.net
  DNS: kpi.stg.etch.samsungds.net
  DNS: automation.stg.etch.samsungds.net
  DNS: ax.stg.etch.samsungds.net
  DNS: sso.stg.etch.samsungds.net
  DNS: fdc.stg.etch.samsungds.net
  DNS: esop.stg.etch.samsungds.net
  DNS: sop.stg.etch.samsungds.net
  DNS: defectmap.stg.etch.samsungds.net
  DNS: voc.stg.etch.samsungds.net
  DNS: teamstaff.stg.etch.samsungds.net
  DNS: mail.stg.etch.samsungds.net
  DNS: llm.stg.etch.samsungds.net
  DNS: mcp.stg.etch.samsungds.net
  DNS: oes.stg.etch.samsungds.net
  DNS: ieq.stg.etch.samsungds.net
  DNS: ai.stg.etch.samsungds.net
  DNS: data.stg.etch.samsungds.net
  DNS: cowork.stg.etch.samsungds.net
  DNS: workspace.stg.etch.samsungds.net
  DNS: tasks.stg.etch.samsungds.net
  DNS: projects.stg.etch.samsungds.net
  DNS: workflow.stg.etch.samsungds.net
  DNS: approval.stg.etch.samsungds.net
  DNS: forms.stg.etch.samsungds.net
  DNS: calendar.stg.etch.samsungds.net
  DNS: wiki.stg.etch.samsungds.net
  DNS: knowledge.stg.etch.samsungds.net
  DNS: assets.stg.etch.samsungds.net
  DNS: inventory.stg.etch.samsungds.net
  DNS: quality.stg.etch.samsungds.net
  DNS: yield.stg.etch.samsungds.net
  DNS: process.stg.etch.samsungds.net
  DNS: recipe.stg.etch.samsungds.net
  DNS: metrology.stg.etch.samsungds.net
  DNS: maintenance.stg.etch.samsungds.net
  DNS: alarm.stg.etch.samsungds.net
  DNS: events.stg.etch.samsungds.net
  DNS: audit.stg.etch.samsungds.net
  DNS: store.stg.etch.samsungds.net
  DNS: etch-sso.samsungds.net
  IP Address: 10.172.26.150
```

- 신청안은 운영 주소 → 테스트 구역의 주소 → 기존 SSO 주소 순서로 정리합니다. 운영·테스트는
  각각 개별 DNS SAN이며 와일드카드·상위 도메인 SAN으로 하위 주소를 대신하지 않습니다.
- 신규 앱 도메인은 같은 클러스터의 공용 APP VIP `10.172.26.150`에 연결하는 전환안입니다.
  DNS 등록·Traefik host 라우팅·앱 공개 URL과 로그인 callback 변경·실제 접속 검증은 별도 작업입니다.
- SSO는 업무 도메인과 다른 IP를 사용합니다. SAN에 SSO 도메인을 포함할 수 있지만, 별도 장비에서
  TLS를 종료한다면 통합 인증서와 개인키를 해당 장비에도 적용해야 합니다. 통합 여부·TLS 종료 위치·
  개인키 배포 정책을 확인하고, SSO를 별도 인증서로 유지하면 기존 SSO DNS 항목을 이 신청안에서 제외합니다.
  예비 `sso.etch.samsungds.net`·`sso.stg.etch.samsungds.net`의 DNS 대상·TLS 종료 위치는 사용 전에 별도로 확정합니다.
- IP SAN은 IP로 직접 접속할 때의 검증용이며 SAN의 모든 도메인을 같은 IP로 제한하지 않습니다.
- FTP 노드 직접 접속과 PostgreSQL·클러스터 내부 Service 주소는 이 HTTPS 인증서 전환안의 대상이 아닙니다.
- CN은 SAN의 누락을 보완하지 않습니다. 목록 밖의 신규 도메인은 SAN을 추가한 인증서 재발급 또는
  별도 인증서 발급이 필요합니다. 목록을 넓혀도 앞으로 모든 주소의 재신청을 없앨 수 있는 것은 아닙니다.
- 예비 주소는 사용자가 요청한 확장 신청을 위한 예약 후보입니다. 서비스별 용도·확정 여부는
  [서비스 원본](services.md#테스트-환경과-예비-주소의-인증서-예약안)에서 관리하며,
  후보의 DNS 등록·Ingress 공개·서비스 설치·권한 부여를 승인하거나 수행한 상태를 뜻하지 않습니다.
- 사용할 주소별 DNS와 Ingress는 별도로 등록하며, 공용 Traefik에서는 실제 사용할 host만 라우팅합니다.
  발급 파일·개인키 보관과 등록은 [인증서 관리](../../certs/README.md)를 따릅니다.

## FTP 직접 접속

아래는 `deploy/ftp/k8s/stack.yaml`의 노드 직접 연결에 필요한 조건입니다.
실제 방화벽 개방·노드별 연결 성공·담당자는 미확인입니다.

| 출발지 | 목적지 | TCP 포트 | 용도·남은 확인 |
| --- | --- | --- | --- |
| 파일 전송 클라이언트의 허용 IP/CIDR | 선택한 FTP 노드의 InternalIP | `6380` | FTP 제어·로그인. 실제 출발지·대상 노드·방화벽 승인 확인 필요 |
| 같은 허용 출발지 | 같은 FTP 노드 InternalIP | `8076–8079` | Passive 목록·업로드·다운로드. 호스트·중간 방화벽과 실제 전송 확인 필요 |

FTP는 `hostNetwork`를 사용하고 Passive 주소에는 해당 노드의 `status.hostIP`를 전달합니다.
업무 APP VIP·Traefik을 경유하지 않는 노드 직접 연결입니다. 현재 절차는 IPv4 InternalIP 직접 접근을 전제하며 NAT·TLS는 별도 설정이 필요합니다.
`FTP_NODES`에 명시한 control plane도 기본적으로 FTP 대상에 포함할 수 있습니다. 접속 경로는 노드별 직접 수신입니다.
노드명·IP는 [서버 목록](servers.md), 배치·데이터는 [FTP 서비스](services.md#ftp-노드별-파일-수신), 실행 방법은 [FTP 설치](../../../ftp/01_SERVER_SETUP.md)를 따릅니다.

## 클러스터 네트워크·실행 기반

| 항목 | 확인 상태·근거 | 남은 확인 |
| --- | --- | --- |
| CNI·Pod/Service CIDR·MTU·DNS domain | 미확인. 구축 기록·각 노드·시스템 리소스 조회 필요 | 네트워크 담당자 확인, Worker 가입·Pod/Service 통신 검증 |

## 추가 확인·변경 연계

| 대상 | 확인할 정보 | 현재 상태 |
| --- | --- | --- |
| 네트워크 접근 | 방화벽 허용 방향·포트·접속 경유지·담당자 | 미확인 |
| VIP·DNS | 기록된 backend·노드 대응·DNS의 최신 상태와 TLS 종료 위치 | 최신 조회 필요 |

VIP backend 변경 시 [서버 목록](servers.md), 공개 URL 변경 시 [서비스 주소](services.md), TLS 입력 변경 시 [인증서 관리](../../certs/README.md)를 대조합니다.
조회·실행 절차는 [현재 환경 확인](../kubernetes/09-baseline.md)과 [VIP 적용](../../ingress/01-VIP.md)을 따릅니다.
