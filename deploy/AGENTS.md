# 서버 배포 지침

## 소유권
- deploy/<app>은 준비된 이미지·chart의 설치, 운영 env, Kubernetes 정의를 소유한다. Portal 제품 코드와 Airflow DAG·플러그인은 apps/<app>이 소유한다.
- 사내 서버의 지원 배포 방식은 Kubernetes뿐이다. Kubernetes 정의가 없으면 전환 미완료로 표시하며 Compose 검증으로 서버 배포 검사를 대체하지 않는다.
- CI Compose·test 입력은 deploy에 유지한다. 외부 PC 전용 설정·mock·실행 도구는 local이 소유하며 서버 실행 도구에서 local을 참조하지 않는다.
- 공통 정의는 deploy/shared 또는 앱별 base에 두고 local은 이를 재사용한다. 앱별 설정을 다른 앱의 디렉터리에 복제하지 않는다.

## 탐색과 검사
- 대상 앱 README → 관련 manifest/env/script → 필요한 shared 계약 순서로 읽는다. 전체 앱의 운영 문서를 선독하지 않는다.
- 앱 경로·그룹 원본은 shared/apps.json, 서버 선택 checkout은 SERVER_CHECKOUT.md를 따른다. 기본 checkout은 소스를 제외하며 빌드할 때만 --with-source로 추가한다.
- 저장소 루트에서 `make server-check APP=<app> PROFILE=prod`로 대상 앱을 검증한다. 렌더·정적 검사와 실제 클러스터 배포 성공을 구분해 보고한다.
- 공통 경로·도구 변경은 `node --test apps/tooling/tests/server-checkout.test.cjs`로 local 없는 서버 경계를 확인한다(전체 개발 checkout에서 실행).
- 실행은 루트 Makefile을 사용한다. 환경·운영 절차는 README.md에서 필요한 항목으로 이동한다.

## 환경과 파일 데이터 계약
- 외부 URL·credential은 env로 주입한다. 승인된 사내 패키지·driver artifact URL만 서버 전용 빌드 입력에 고정할 수 있다. 버전이 명시되고 credential·사용자별 endpoint가 아니며 local 개발에 사용되지 않고 docs/configuration.md에 문서화된 경우에 한한다.
- 새로 추가하거나 변경하는 API 업무 파일은 컨테이너의 /data/<domain> 아래에 마운트한다. domain은 lowercase snake_case다.
- Django는 <DOMAIN>_DATA_ROOT로 컨테이너 경로를 노출한다. 개별 파일 경로가 원본 계약일 때만 <DOMAIN>_<NAME>_PATH를 쓴다.
- 참고·원본 데이터는 Kubernetes readOnly: true로 마운트한다. 업로드·생성물·처리 큐 등 앱 소유 데이터만 쓰기를 허용한다.
- 호스트 경로는 env 기반으로 유지하고 기존 공유 경로가 있으면 재사용한다. Compose 마운트를 추가할 경우 `${<DOMAIN>_DATA_HOST_PATH:-../../../data/<domain>}` 및 읽기 전용 `:ro` 규칙을 적용한다.
- API 마운트 변경 시 portal/k8s의 base·운영 overlay, local/portal/k8s의 대응 overlay와 local/shared의 호스트 매핑, 양쪽 Portal env 및 docs/configuration.md를 함께 맞춘다. 이는 개발 checkout의 동기화 규칙이며 서버 실행이 local 파일을 요구해서는 안 된다.
- 새 /appdata 경로를 만들지 않는다. 기존 /appdata 계약을 수정할 때 /data/<domain>으로 이관한다.
