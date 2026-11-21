# 서버 파일 받기

[공통 안내](../README.md) · 다음: [배포 준비와 검증](02-deploy.md)

관리 호스트에 저장소 전체를 clone하고 Git으로 갱신하는 방법입니다. 사람과 사내 `ops` agent가 같은 checkout을 사용합니다([운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)).

- [저장소 clone](#저장소-clone)
- [Git·운영 파일 관리](#git운영-파일-관리)
- [운영 기록](#운영-기록)

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

**기대 결과:** 배포할 커밋이 표시되고 저장소 루트에 Makefile·`deploy/`·`docs/`가 있습니다. 실제 checkout 경로를 [운영 기록](#운영-기록)에 남깁니다.

**실패 확인:** 인증·네트워크 오류면 URL과 배포 계정의 Git 인증(SSH 키 또는 저장된 credential)이 관리 호스트에 있는지 확인합니다. Git에 없는 파일(인증서·외부 env·개인키)은 clone으로 전달되지 않으며 [인증서 발급](../infrastructure/access.md#인증서-발급)과 [운영 입력 파일](../infrastructure/access.md#운영-입력-파일) 절의 방법으로 따로 둡니다.

### 운영 agent 작업 루트

이 checkout 하나를 사람과 사내 opencode `ops` agent가 함께 씁니다. checkout 루트를 opencode의 작업 루트로 열고 `ops`를 선택합니다.
`ops` agent는 [agent 정의](../../../../.opencode/agents/ops.md)와 [운영 agent 지침](../../../AGENTS.md#사내-운영-agent)을 따르고, 작업 시작 때 [공통 시작](../../../README.md#모든-작업-공통-시작)의 추적 변경 검사와 fast-forward 갱신을 실행합니다.
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

추적 파일 변경이 있으면 내용을 확인합니다. 다음 단계의 pull이 충돌로 실패하면 관련 파일을 보고합니다. 진행 내역이 공유 문서에 쌓여 있다면 필요에 따라 아래 운영 기록으로 옮길 수 있습니다.
원격 저장소와 배포 브랜치가 [저장소 원본](../infrastructure/repositories.md#공통-주소와-경로-규칙)의 값과 맞는지 확인합니다.

`identity.env`를 Git이 추적하던 checkout에서는 로컬에 입력한 값이 있다면 갱신 전에 보관합니다.

[변경] 관리 호스트의 저장소 루트에서 이전 입력 파일을 소유자 전용으로 복사합니다.

```bash
identity_backup=$(mktemp "$HOME/.identity.env.before-pull.XXXXXX") &&
  install -m 0600 identity.env "$identity_backup" &&
  stat -c '%a %n' "$identity_backup"
```

출력의 `600`과 파일 경로를 확인합니다. 로컬 변경으로 pull이 멈추면 이 경로를 보관한 채 충돌 파일을 보고합니다. 갱신 후 루트 파일이 없어졌으면 [공용 운영 입력 준비](02-deploy.md#공용-운영-입력-준비)의 복사 단계에서 보관한 파일을 원본으로 사용합니다.

### 2. 갱신

[변경] [모든 작업 공통 시작](../../../README.md#모든-작업-공통-시작)의 첫 명령 블록을 실행합니다.

**기대 결과:** 배포할 커밋이 표시됩니다. 개발 PC의 미커밋·미추적 파일은 전달되지 않습니다.
Git 갱신은 파일만 바꾸며 Kubernetes 리소스·Secret·DB·실행 중인 Pod를 변경하지 않습니다.

**실패 확인:** fast-forward가 불가능하거나 원격에 닿지 않으면 기존 변경을 보존하고 실패한 명령과 오류를 보고합니다.

### 3. 다음 단계

갱신으로 commit이 바뀌었고 이미 앱이 배포된 서버면 [전환 런북](05-transition.md)의 `적용 여부 확인`을 먼저 실행합니다.
변경 유형별 검사·적용은 [운영 절차의 업데이트](03-operations.md#업데이트--관리-호스트)를 따릅니다.

## 운영 기록

일상 진행 이력과 점검 상태는 관리 호스트에서 `ops`를 실행하는 계정의 `~/.local/state/tailwind/ops/`에 기록하는 것을 권장합니다. 배포 checkout을 새로 받아도 같은 계정의 기록을 다시 사용할 수 있습니다.

| 파일 | 내용 |
| --- | --- |
| `state.md` | context·앱별 최신 관측값, 성공·실패·미확인 상태, 남은 작업, 다음 확인 명령. 같은 항목은 현재값으로 갱신 |
| `progress.md` | 작업 일시, context, checkout commit, 실행한 단계, 결과·근거, 막힌 단계와 재개 방법. 새 항목을 뒤에 추가 |

[변경] checkout 밖에 기록할 때 디렉터리를 준비합니다.

```bash
install -d -m 0700 ~/.local/state/tailwind/ops
ls -ld ~/.local/state/tailwind/ops
```

성공은 해당 디렉터리가 배포 계정 소유이고 권한이 `drwx------`인 상태입니다. 파일은 기록할 때 만듭니다. 권한 오류는 운영 계정과 홈 디렉터리 접근을 확인합니다.

작업을 시작할 때 [공유 대기 목록](../infrastructure/pending.md)과 기존 `state.md`를 참고할 수 있습니다. 공유가 필요한 운영값과 접근 경로는 [인프라 원본의 기록 규칙](../infrastructure/README.md#기록-규칙)에 따라 갱신할 수 있습니다. 비밀번호·토큰·개인키·kubeconfig 본문은 적지 않습니다.

[조회] 공유 원본을 수정했다면 배포 checkout 루트에서 Git 추적 파일 상태를 확인합니다.

```bash
git status --short --untracked-files=no
```

수정한 추적 파일과 변경 이유를 작업 결과에 포함합니다.
