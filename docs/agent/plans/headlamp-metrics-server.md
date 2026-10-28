# ExecPlan: Headlamp 사용량 조회용 metrics-server

## 목표
- 프로젝트의 사내 registry.k8s.io 미러 주소를 넣은 metrics-server 설치 파일을 제공한다.
- 서버에서 GitHub 다운로드 없이 루트 Makefile로 설치하고 Metrics API를 확인한다.
- 사용자의 추가 요청에 따라 metrics-server의 kubelet 인증서 검증을 생략한다.

## 현재 상태
- 사용자 클러스터는 Kubernetes v1.36.4이며 초기 설치 전에는 v1beta1.metrics.k8s.io APIService가 없었다.
- 설치 후 khplanew01의 kubelet 인증서에 IP SAN이 없어 수집이 실패했고, 사용자가 인증서 검증 생략을 요청했다.
- docs/integrations/proxy-mirrors.md는 registry.k8s.io의 미러 이름을 proxy-docker-registry.k8s.io로 정의한다.
- Docker 이미지 주소 형식은 repository.samsungds.net/<mirror>/<image>:<tag>이다.
- 공식 metrics-server v0.9.0 components.yaml과 이미지 manifest의 외부 응답을 확인했다.

## 범위
- deploy/shared/metrics-server/components.yaml, 루트 Makefile, Headlamp 운영 안내.
- Monitoring 설정, Headlamp 인증 설정과 기존 배포 명령은 변경하지 않는다.

## 설계
- 공식 v0.9.0 manifest를 저장소에 포함하고 이미지 주소를 사내 미러로 치환한다.
- metrics-server 인자에 --kubelet-insecure-tls를 추가해 모든 수집 대상 kubelet의 인증서 검증을 생략한다.
- 사용자의 명시 요청에 따라 사내 이미지 주소를 설치 YAML에 넣는다.
- 공식 ServiceAccount·RBAC·Service·Deployment·APIService 구성을 유지한다.
- metrics-server-up은 명시한 KUBE_CONTEXT에 적용하고 Deployment와 APIService 준비를 기다린다.
- 데이터베이스·제품 API·기존 env 계약은 바꾸지 않는다.

## 실행 단계
- [x] 사내 미러 이미지가 지정된 공식 manifest 추가.
- [x] Makefile 실행 진입점과 Headlamp 운영 절차 추가.
- [x] 원본 대비 차이·YAML·Make 명령·서버 checkout 경계 검증.
- [x] kubelet 인증서 검증 생략 옵션과 재적용 절차 추가·검증.

## 검증
- 공식 manifest와 비교해 이미지·요청된 kubelet TLS 인자 외 리소스 정의가 같은지 확인한다.
- YAML 파싱과 Kubernetes 리소스 참조·이미지·포트 연결을 검사한다.
- make -n metrics-server-up KUBE_CONTEXT=validation-context 및 빈 context 차단 확인.
- node --test apps/tooling/tests/server-checkout.test.cjs
- make server-check APP=headlamp PROFILE=prod
- 실제 사내 클러스터 적용·미러 pull은 이 외부 환경에서 수행하지 않는다.

## 위험과 대응
- 위험: 사내 미러 인증·CA·네트워크, kubelet 인증서·접근 여부는 외부 환경에서 확인할 수 없다.
- 대응: 운영 문서에 준비 상태 검사와 실패 시 진단 명령을 제공한다. 인증서 검증 생략 범위와 인증서 정상화 후 옵션 제거 절차를 기록한다.

## 진행 기록
- 2026-10-28: 미러 참고표에서 실제 경로를 확인했으며 공식 v0.9.0 구성으로 설치 파일을 준비한다.
- 2026-10-28: 공식 원본 대비 변경은 이미지 주소와 한국어 출처 주석뿐임을 확인했다. YAML 9개 리소스 파싱·참조·포트 연결 및 kubectl kustomize 렌더가 통과했다.
- 2026-10-28: Make 명령 dry-run과 빈 context 차단을 확인했다. 서버 checkout 검사 30개가 통과했고 git diff --check도 통과했다.
- 2026-10-28: 기본 PATH에서 helm을 찾지 못했으나, Git 마무리 전에 저장소의 .tools/bin/helm을 확인했다. `HELM_BIN="$PWD/.tools/bin/helm" make server-check APP=headlamp PROFILE=prod`가 통과했다. 사내 미러 pull과 실제 클러스터 설치는 서버에서 별도 확인한다.
- 2026-10-28: 사용자가 kubelet 인증서 검증 생략을 명시 요청했다. 설치 YAML과 운영 안내에 옵션을 반영하고 기존 설치에 재적용할 수 있도록 한다.
- 2026-10-28: YAML·kubectl kustomize 렌더에서 옵션이 한 번만 포함되는지와 기존 구성 대비 해당 인자만 추가됐는지 검증했다. Headlamp server-check, Make dry-run, 서버 checkout 테스트 30개와 git diff --check가 통과했다. 실제 서버 재적용은 수행하지 않았다.
