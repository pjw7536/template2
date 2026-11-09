# 서버 배포 지침

## 소유권과 실행 경계

- `deploy/<app>`은 준비된 이미지·chart의 설치, 운영 env, Kubernetes 정의를 소유한다. 제품 코드와 Airflow DAG·플러그인은 `apps/<app>`이 소유한다.
- 사내 서버의 지원 배포 방식은 Kubernetes뿐이다. 정의가 없으면 전환 미완료로 표시하며 Compose 검증으로 대신하지 않는다.
- CI Compose·test 입력은 `deploy`, 외부 PC 설정·mock·실행 도구는 `local`이 소유한다. 서버 검사·렌더·배포는 `local`·앱 소스·루트 `docs` 없이 실행할 수 있어야 한다.
- 공통 정의는 `deploy/shared` 또는 앱별 base에 둔다. local은 이를 재사용하며 앱별 설정을 다른 앱에 복제하지 않는다.
- 실행 진입점은 루트 Makefile이다. 앱 경로·그룹 원본은 [apps.json](shared/apps.json), 서버 파일 준비는 [선택 checkout](shared/docs/operations/01-checkout.md#선택-checkout)을 따른다. 소스는 빌드에 필요한 경우에만 `--with-source`로 추가한다.

## 탐색과 운영 정보

1. [사내 인프라 정보](shared/docs/infrastructure/README.md)와 작업 주제의 원본을 읽는다. 분류·기록 규칙과 하위 AGENTS.md를 따른다.
2. 대상 앱 README에서 준비·설치·운영 문서를 선택하고 관련 manifest·env·script와 필요한 shared 계약을 확인한다.
3. 저장소 선언·안내 예시·사용자 확인·서버 조회를 구분한다. 정적 검사 통과를 실제 서버 적용·접속 성공으로 단정하지 않는다.
4. 새 운영 정보를 받으면 주제별 원본의 현재 값·연결 관계·설정 원본·확인 상태·남은 확인을 갱신한다. 정보 기록 요청을 서버 적용 요청으로 확대하지 않는다.

실행 설정의 원본은 소유 앱의 manifest·env·Helm values다. 운영값을 다른 안내에 복제하지 않으며,
비밀값은 문서에 쓰지 않는다. 확인 날짜·변경 경위·이전 값은 Git 이력으로 추적하고 현재 필요한 이전·복구 절차는 유지한다.

## 문서 구조와 작성

- 사람용 진입점은 [배포 README](README.md), 공통 문서는 [공통 색인](shared/docs/README.md)에서 연결한다.
- 공통 절차는 `shared/docs/`의 `kubernetes/`·`ingress/`·`certificates/`·`operations/`·`configuration/`에 둔다. `infrastructure/`는 현재 운영 정보 원본이다.
- `shared/ingress/`는 실행 코드·manifest, `shared/certs/`는 인증서·CA 파일을 소유한다. 상세 절차는 공통 문서에서 관리한다.
- 앱 README에는 역할·의존 서비스·설치 순서·완료 기준·운영 링크를 둔다. 상세 절차는 `<app>/docs/`에서 `01-setup.md`처럼 두 자리 번호와 역할 이름을 조합해 관리한다. 준비·설치·운영 단위로 통합하고 앱별 읽기 순서의 연속 번호를 붙인다. 짧은 참고만으로 파일을 늘리지 않는다.
- Job·overlay·입력 템플릿 옆 README는 해당 원본의 역할·사용 조건·상세 절차 링크를 설명한다. 같은 실행 명령의 전체 절차를 반복하지 않는다.
- 절차에는 목적·준비물, 실행 위치·입력, 명령, 기대 결과·실패 확인, 다음 단계를 명시한다. 명령의 대상과 조회·검사·적용·삭제 영향을 구분한다.
- 문서 번호를 실행 파일의 번호로 해석하지 않는다. 앱 문서의 파일 번호는 권장 읽기 순서, 역할 이름은 내용을 나타내며 본문의 단계 번호는 각 문서 안의 실제 실행 순서를 나타낸다. 공통 문서는 주제별 역할 이름을 유지한다.
- 이동 시 내부 링크와 도구의 안내 경로를 현재 원본으로 갱신한다. 이전 경로·앵커의 호환 안내는 보존 요청이 있을 때만 둔다.

## 환경과 데이터 계약

- 외부 URL·credential은 env로 주입한다. 승인된 사내 패키지·driver artifact URL만 서버 전용 빌드 입력에 고정할 수 있다. 버전이 명시되고 credential·사용자별 endpoint가 아니며 local에서 사용하지 않고 `docs/reference/01-configuration.md`에 문서화된 경우에 한한다.
- 새로 추가하거나 변경하는 API 업무 파일의 컨테이너 경로는 `/data/<domain>`이다. domain은 lowercase snake_case다.
- Django는 `<DOMAIN>_DATA_ROOT`로 컨테이너 경로를 노출한다. 개별 파일 경로가 원본 계약일 때만 `<DOMAIN>_<NAME>_PATH`를 쓴다.
- 참고·원본 데이터는 Kubernetes `readOnly: true`로 마운트한다. 업로드·생성물·처리 큐 등 앱 소유 데이터만 쓰기를 허용한다.
- Worker의 앱 소유 호스트 경로는 `/appdata/<app 또는 domain>` 아래로 통일한다. 설정 가능한 경로는 env 기반으로 유지하고 기존 공유 경로는 재사용한다.
- 기존 PV·데이터를 자동 이동·삭제하지 않는다. 경로 변경에는 백업·데이터 이전·PV/PVC 전환을 별도로 준비한다.
- `/appdata` 통일은 kubelet·container runtime·node-exporter 시스템 경로와 동적 StorageClass 저장 위치에 적용하지 않는다. 컨테이너의 `/data/<domain>` 계약과 구분한다.
- Compose 마운트를 추가할 때는 `${<DOMAIN>_DATA_HOST_PATH:-../../../data/<domain>}` 및 읽기 전용 `:ro` 규칙을 적용한다. 외부 PC의 kind 호스트 매핑은 local overlay에 명시한다.

API 마운트 변경 시 다음 원본을 함께 맞춘다. 이는 전체 개발 checkout의 동기화 규칙이며 서버 실행이 local 파일을 요구해서는 안 된다.

- `portal/k8s`의 base·운영 overlay와 `local/portal/k8s`의 대응 overlay
- `local/shared`의 호스트 매핑과 양쪽 Portal env
- `docs/reference/01-configuration.md`

## 검증과 보고

- 배포 정의 변경은 저장소 루트에서 `make server-check APP=<app> PROFILE=prod`로 확인한다. 실제 입력·클러스터 조회·적용·접속 결과는 별도로 보고한다.
- 문서 변경은 상대 링크·앵커, `git diff --check`, `make audit-docs`를 확인한다. 문서 이동 시 삭제한 경로·앵커의 참조가 남지 않았는지와 정보 보존도 확인한다.
- 공통 경로·도구 변경과 문서 이동은 전체 개발 checkout에서 `node --test apps/tooling/tests/server-checkout.test.cjs`로 local 없는 서버 경계를 확인한다.
- 변경 경로·핵심 내용·검증 결과·실제 서버 조회 여부·남은 확인을 보고한다. 사용자 요청 없이 commit·push하지 않는다.
