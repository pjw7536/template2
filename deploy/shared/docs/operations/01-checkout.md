# 서버 파일 받기

[공통 안내](../README.md) · 다음: [배포 준비와 검증](02-deploy.md)

관리 호스트에 저장소 전체를 clone하고 Git으로 갱신하는 방법입니다. 사람과 사내 `ops` agent가 같은 checkout을 사용합니다([운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)).

- [저장소 clone](#저장소-clone)
- [Git·운영 파일 관리](#git운영-파일-관리)

## 저장소 clone

### 1. 준비물과 실행 위치

| 항목 | 내용 |
| --- | --- |
| 실행 위치 | 관리 호스트. 앱 Pod와 데이터가 놓이는 Worker는 앱별 배포 정의가 정합니다 |
| checkout 경로 | 예시 `/appdata/etchax`. 실제 경로는 [운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)가 원본입니다 |
| 입력 | 사내 Git 저장소 URL·배포 브랜치. 현재 값은 [저장소 원본](../infrastructure/repositories.md#공통-주소와-경로-규칙)에서 확인합니다 |
| 전제 | 변경사항이 Git에 반영된 상태. 인증서와 DB 데이터는 기존 서버 경로에 유지합니다 |

### 2. 처음 clone

[변경] 관리 호스트에 checkout이 아직 없을 때 한 번 실행합니다. `<checkout 경로>`가 이미 있으면 clone하지 않고 [Git·운영 파일 관리](#git운영-파일-관리)로 갑니다. `GIT_TERMINAL_PROMPT=0`은 Git이 계정을 묻지 않고 실패하게 합니다.

```bash
GIT_TERMINAL_PROMPT=0 git clone --branch "<배포 브랜치>" "<사내 Git 저장소 URL>" "<checkout 경로>"
git -C "<checkout 경로>" log -1 --oneline
ls -d "<checkout 경로>/Makefile" "<checkout 경로>/deploy" "<checkout 경로>/docs"
```

**기대 결과:** 배포할 커밋이 표시되고 저장소 루트에 Makefile·`deploy/`·`docs/`가 있습니다. 실제 checkout 경로를 [운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)에 기록합니다.

**실패 확인:** 인증·네트워크 오류면 URL과 배포 계정의 Git 인증(SSH 키 또는 저장된 credential)이 관리 호스트에 있는지 확인합니다. Git에 없는 파일(인증서·외부 env·개인키)은 clone으로 전달되지 않으며 [인증서 발급](../infrastructure/access.md#인증서-발급)과 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일) 절의 방법으로 따로 둡니다.

### 운영 agent 작업 루트

이 checkout 하나를 사람과 사내 opencode `ops` agent가 함께 씁니다. checkout 루트를 opencode의 작업 루트로 열고 `ops`를 선택합니다.
`ops` agent는 루트 `AGENTS.md`의 개발 규칙 대신 [agent 정의](../../../../.opencode/agents/ops.md)와 [운영 agent 지침](../../../AGENTS.md#사내-운영-agent)을 따르고, 작업 시작 때 `git pull --ff-only`로 갱신합니다.
이미지 빌드도 이 checkout에서 합니다. 빌드 도구는 [이미지 빌드 도구](../../../README.md#이미지-빌드-도구)의 `make build-tools-install`로 설치합니다.

**다음 단계:** [배포 준비와 검증](02-deploy.md#배포-준비)

## Git·운영 파일 관리

checkout·env·인증서·kubeconfig·데이터 위치는
[운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)가 원본입니다.
실제 DB·업무 데이터는 PV/PVC·Worker·외부 저장소에 있어 checkout 복사로 백업되지 않습니다.
작업을 시작할 때의 갱신은 [모든 작업 공통 시작](../../../README.md#모든-작업-공통-시작)의 1번과 같습니다.

### 1. 갱신 전 확인 — 관리 호스트

[조회] 배포 checkout 루트에서 실행합니다.

```bash
git status --short
git remote -v
git branch --show-current
git rev-parse HEAD
```

변경 파일이 있으면 내용을 확인하고 보존합니다. 변경을 없애기 위해 강제 초기화하지 않습니다.
원격 저장소와 배포 브랜치가 [저장소 원본](../infrastructure/repositories.md#공통-주소와-경로-규칙)의 값과 맞는지 확인합니다.

### 2. 갱신

[변경] checkout의 파일만 바꿉니다.

```bash
git pull --ff-only
git log -1 --oneline
```

**기대 결과:** 배포할 커밋이 표시됩니다. 개발 PC의 미커밋·미추적 파일은 전달되지 않습니다.
Git 갱신은 파일만 바꾸며 Kubernetes 리소스·Secret·DB·실행 중인 Pod를 변경하지 않습니다.

**실패 확인:** fast-forward가 불가능하거나 원격에 닿지 않으면 현재 checkout으로 진행하고 실패한 명령과 오류를 보고에 남깁니다. `git reset`·`git stash`·`git checkout`으로 로컬 커밋·변경을 지워 맞추지 않습니다.

### 3. 다음 단계

갱신으로 commit이 바뀌었고 이미 앱이 배포된 서버면 [전환 런북](05-transition.md)의 `적용 여부 확인`을 먼저 실행합니다.
변경 유형별 검사·적용은 [운영 절차의 업데이트](03-operations.md#업데이트--관리-호스트)를 따릅니다.
