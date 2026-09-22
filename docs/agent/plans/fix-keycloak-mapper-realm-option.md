# ExecPlan: Keycloak mapper realm 옵션 교정

## 목표
- 사용자 요청의 sed 치환을 claim Job 실행 전에 적용한다.

## 현재 상태
- 관리 스크립트가 대상 realm에 --realm 옵션을 사용한다.
- Job에는 배포 YAML이 없고 ConfigMap 스크립트가 읽기 전용으로 마운트된다.

## 범위
- mapper 원본, Job 명령, 생성 YAML과 검증.

## 설계
- 원본의 대상 realm 옵션을 -r로 변경하고 관리자 로그인 --realm master는 유지한다.
- 기존 ConfigMap도 지원하도록 Job이 /tmp로 복사한 스크립트에 sed 치환과 백업을 적용한다.
- credential, realm 데이터, 네트워크 설정은 변경하지 않는다.

## 실행 단계
- [x] 원본·Job 수정 및 YAML 생성
- [x] 셸 문법·Job 실행 명령·환경 회귀 검증

## 검증
- bash -n deploy/k8s/keycloak/sync-oidc-claim-mappers.sh
- make k8s-export, make k8s-render
- node --test scripts/tests/environment.test.cjs
- 임시 파일로 Job의 복사·치환·실행 명령 검증
- git diff --check

## 위험과 대응
- 완료된 Job은 재생성이 필요하다. 원본 ConfigMap은 Job에서 수정하지 않는다.
- 운영 Keycloak에 직접 접속하지 않으므로 실제 관리 API 성공 여부는 배포 후 확인한다.

## 진행 기록
- 2026-09-14: 요청한 치환을 읽기 전용 마운트와 호환되도록 설계했다.

- 2026-09-14: 셸 문법, Kustomize 렌더링과 환경 회귀 23개 통과. Job 명령은 기존 스크립트를 변경하지 않고 사본 치환·백업·실행하는 것을 확인했다. 재시도 시 읽기 전용 사본 교체를 위해 cp -f를 사용한다. 운영 적용은 하지 않았다.
