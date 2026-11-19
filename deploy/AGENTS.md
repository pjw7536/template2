# 서버 배포 지침

## 소유권과 실행 경계

- `deploy/<app>`은 준비된 이미지·chart의 설치·운영 env·Kubernetes 정의를 소유한다. 제품 코드와 Airflow DAG·플러그인은 `apps/<app>`, 외부 PC 설정·mock·실행 도구는 `local/<app>`, CI Compose·test 입력은 deploy가 소유한다.
- 사내 서버 배포는 Kubernetes만 지원한다. 정의가 없으면 전환 미완료로 표시하고 Compose 검증으로 대신하지 않는다.
- 서버 검사·렌더·배포는 local·앱 소스·루트 docs 없이 실행되어야 한다. 공통 정의는 `shared` 또는 앱별 base에 두고 local에서 재사용한다. 다른 앱에 설정을 복제하지 않는다.
- 진입점은 루트 Makefile, 앱·그룹 원본은 [apps.json](shared/apps.json), 파일 준비는 [서버 파일 받기](shared/docs/operations/01-checkout.md)다.

## 탐색과 문서

- 대상 앱 README → 작업별 설치·운영 문서 → 관련 manifest·env·script → 필요한 shared 계약 순으로 확인한다.
- 인프라 정보의 분류·확인 상태·갱신은 [인프라 README](shared/docs/infrastructure/README.md)와 [하위 지침](shared/docs/infrastructure/AGENTS.md)을 따른다. 실제 설정 원본은 소유 앱 manifest·env·Helm values이며 운영값을 다른 안내에 복제하지 않는다. 비밀값은 문서에 쓰지 않는다.
- 정적 검사와 실제 서버 적용·접속 성공을 구분하고, 정보 기록 요청을 서버 적용 요청으로 확대하지 않는다.
- 사람용 진입점은 [배포 README](README.md)와 [공통 색인](shared/docs/README.md)이다. 공통 절차는 `shared/docs/{kubernetes,ingress,certificates,operations,configuration}/`, 현재 운영 정보는 `infrastructure/`에서 관리한다.
- `shared/ingress`는 실행 코드·manifest, `shared/certs`는 인증서·CA 파일을 소유한다. 상세 절차는 공통 문서에 둔다.
- 앱 README는 역할·의존 서비스·설치 순서·완료 기준·운영 링크를 제공한다. 상세 문서는 `<app>/docs/01-setup.md`처럼 두 자리 연속 번호와 역할 이름으로 준비·설치·운영 단위로 통합한다. 짧은 참고만으로 파일을 늘리지 않는다.
- Job·overlay·입력 템플릿 옆 README는 원본의 역할·사용 조건·상세 절차 링크만 설명하고 전체 명령을 반복하지 않는다.
- 절차에는 목적·준비물·실행 위치·입력·명령·기대 결과·실패 확인·다음 단계를 명시하고 조회·검사·적용·삭제 영향을 구분한다. 문서 번호는 권장 읽기 순서이며 본문의 단계 번호나 실행 파일 번호와 구분한다. 공통 문서는 주제별 역할 이름을 유지한다.
- 문서 이동 시 내부 링크·도구 안내 경로를 갱신한다. 이전 경로·앵커 호환 안내는 보존 요청이 있을 때만 둔다.

## 환경과 데이터 계약

- 승인된 사내 패키지·driver artifact URL만 서버 전용 빌드 입력에 고정할 수 있다. 버전 명시, credential·사용자별 endpoint가 아님, local 미사용, `docs/reference/01-configuration.md` 문서화 조건을 모두 만족해야 한다. 그 외 URL·credential은 루트 env 원칙을 따른다.
- 새로 추가·변경하는 API 업무 파일의 컨테이너 경로는 `/data/<domain>`이며 domain은 lowercase snake_case다. Django는 `<DOMAIN>_DATA_ROOT`를 노출하고 개별 파일이 원본 계약일 때만 `<DOMAIN>_<NAME>_PATH`를 쓴다.
- 참고·원본 데이터는 Kubernetes `readOnly: true`, 업로드·생성물·처리 큐 등 앱 소유 데이터만 쓰기를 허용한다.
- Worker의 앱 소유 호스트 경로는 `/appdata/<app 또는 domain>`이다. 설정 가능한 경로는 env로 유지하고 기존 공유 경로를 재사용한다. kubelet·container runtime·node-exporter 시스템 경로와 동적 StorageClass 저장 위치는 이 통일 규칙의 대상이 아니며 컨테이너 경로와 구분한다.
- 기존 PV·데이터를 자동 이동·삭제하지 않는다. 경로 변경에는 백업·데이터 이전·PV/PVC 전환을 별도로 준비한다.
- Compose 마운트는 `${<DOMAIN>_DATA_HOST_PATH:-../../../data/<domain>}`와 읽기 전용 `:ro`를 적용한다. 외부 PC kind 호스트 매핑은 local overlay에 명시한다.
- API 마운트 변경은 `portal/k8s` base·운영 overlay, `local/portal/k8s`, `local/shared` 호스트 매핑, 양쪽 Portal env, `docs/reference/01-configuration.md`를 함께 맞춘다. 이는 전체 개발 checkout의 동기화 규칙이며 서버 실행의 local 의존성을 뜻하지 않는다.

## 검증

- 배포 기록·대조 도구: `python3 -m unittest discover -s deploy/shared/tests -p 'test_deploy_state.py'`. 앱을 추가하면 `apps.json`의 `runtime.namespace`(공유 namespace는 `selector`)를 함께 정한다.
- 배포 정의: 루트 `make server-check APP=<app> PROFILE=prod`. 실제 입력·클러스터 조회·적용·접속은 별도로 보고한다.
- 문서: 상대 링크·앵커, `git diff --check`, `make audit-docs`. 이동 시 삭제 경로·앵커 참조와 정보 보존을 확인한다.
- 공통 경로·도구 변경과 문서 이동: 전체 개발 checkout에서 `node --test apps/tooling/tests/server-checkout.test.cjs`로 서버 독립 실행을 확인한다.
- 보고에는 변경 내용·검증 결과와 실제 서버 조회 여부·남은 확인을 구분한다.
