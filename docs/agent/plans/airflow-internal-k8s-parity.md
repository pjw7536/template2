# ExecPlan: Airflow 사내 설정 Kubernetes 이관 정합성

## 목표
- 기존 사내 Dockerfile·Compose 빌드 설정과 ODBC 파일 전달을 Kubernetes 배포 기본값에 반영한다.

## 현재 상태
- 기존 Dockerfile을 재사용하지만 새 build.env 예시는 공개 이미지와 설치 비활성 기본값이다.
- 기존 사내 설정은 airflow.internal.yml의 build args에 있으며 ODBC 디렉터리를 읽기 전용으로 마운트한다.
- 현재 외부 PC에는 ODBC 실파일과 사내 연결이 없다. 실제 운영 env 파일은 아직 없다.

## 범위
- deploy/airflow 환경 예시·빌드/볼륨 연결·회귀 테스트·관련 문서.
- 로컬 Compose, 사용자 인증값, DAG/API 계약, 실제 클러스터·DB는 변경하지 않는다.

## 설계
- 사내 base/PostgreSQL 이미지, APT/PIP mirror, BigDataQuery 설치 true, versioned driver URL을 env 입력 기본값으로 옮긴다.
- 단일 노드에서 기존 ODBC 디렉터리를 /usr/local/odbc에 read-only hostPath로 전달한다. 기존 Secret 방식도 명시적 대안으로 유지한다.
- 기존 Compose와 차이가 나는 scheduler·pool 기본값은 확인한 원본 기준으로 정렬하며 변경 내용을 기록한다.
- 예시는 사용자 승인 사내 주소를 포함하되 URL은 Python·Dockerfile에 고정하지 않고 env로 주입한다.

## 실행 단계
- [x] 기존 build args와 런타임 차이 확인
- [x] 사내 기본값·ODBC 디렉터리 및 검증 반영
- [x] Helm 실행 옵션 정합성과 문서 반영
- [x] 회귀·렌더·로컬 Compose 불변 검증

## 검증
- 모든 기존 사내 build arg와 PostgreSQL 이미지의 일치 테스트
- 실제 Dockerfile 재사용과 공백 포함 PIP_TRUSTED_HOST 전달 테스트
- ODBC hostPath/Secret 상호 배타·읽기 전용·대상 경로 검사
- 공식 chart lint/template, Airflow bootstrap 테스트, 기존 인프라 테스트
- 문서 감사와 git diff --check

## 위험과 대응
- 사내 패키지 다운로드·ODBC DB 연결은 외부 PC에서 재현할 수 없으므로 성공으로 보고하지 않는다.
- 기존 ODBC 디렉터리 파일은 운영 서버의 절대 경로로 지정해야 하며 빈 설정을 생성하지 않는다.
- 신규 DAG 자동 실행 동작이 기존 Compose와 같아지므로 이전 중 기존 scheduler를 멈추고 DB의 pause 상태를 확인한다.

## 진행 기록
- 2026-09-14: 사내 설정을 그대로 적용하라는 사용자 지시에 따라 시작.

- 기존 사내 build arg 전체와 PostgreSQL image 일치, Dockerfile 원본 재사용·공백 포함 인자 전달을 테스트로 확인했다.
- 단위·Helm 통합 18개 및 기존 인프라 테스트 전체 43개 통과. 모든 Airflow Deployment와 초기화 Job의 ODBC hostPath·읽기 전용·동일 노드 배치를 렌더 결과에서 확인했다.
- 사내 의존성 없이 공개 기본값으로 만든 검증 이미지에서 ODBC 환경변수 상속, PostgreSQL migration, 관리자 생성·재실행, default_pool=-1, DAG 8개 import, 실제 차트 설정과 Basic Auth API 응답을 확인했다. 사내 패키지 설치 성공을 의미하지 않는다.
- make server-check APP=airflow, 문서 감사, 기존 Compose config, Python 문법, README shell 문법, git diff --check 통과. 원래 Dockerfile·사내 Compose·외부 로컬 입력의 파일 내용 불변 확인.
- 실제 운영 build.env/k8s.env가 아직 없어 덮어쓰지 않았다. 새 사내 기본값은 서버에서 복사해 사용할 공개 예시에 반영했다.
- 실제 Kubernetes 배포·DB 이전·사내 네트워크 접속·commit/push는 실행하지 않았다.
