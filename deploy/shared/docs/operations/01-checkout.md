# 서버 파일 받기

[공통 안내](../README.md) · 다음: [배포 준비와 검증](02-deploy.md)

관리 호스트에 저장소를 clone하고 Git으로 갱신하는 방법입니다. 사람용 전체 checkout과 사내 `ops` 전용 checkout은 별도 디렉터리에서 같은 Git 브랜치를 사용합니다([운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)).

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

```bash
read -r -p '사내 Git 저장소 URL: ' ETCHAX_REPO_URL
read -r -p '배포 브랜치: ' ETCHAX_DEPLOY_BRANCH

git clone --branch "$ETCHAX_DEPLOY_BRANCH" "$ETCHAX_REPO_URL" /appdata/etchax
cd /appdata/etchax
git log -1 --oneline
```

**기대 결과:** 배포할 커밋이 표시되고 저장소 루트에 Makefile·`deploy/`·`docs/`가 있습니다.

**실패 확인:** 인증·네트워크 오류면 사내 Git 접근 권한과 URL을 확인합니다. Git에 없는 파일(인증서·외부 env·개인키)은 clone으로 전달되지 않습니다.

### ops 전용 checkout

관리 호스트에서 사람이 한 번 준비합니다. 아래 경로는 새 checkout의 예시입니다. 기존 전체 checkout은 운영 파일·로컬 변경·반입물이 있으므로 그대로 둡니다. 이미지 빌드는 소스가 있는 전체 checkout에서 진행합니다.

```bash
(
  set -e
  git clone --branch "$ETCHAX_DEPLOY_BRANCH" "$ETCHAX_REPO_URL" /appdata/etchax-ops
  cd /appdata/etchax-ops
  ./deploy/shared/scripts/apply-ops-checkout.sh
  git rev-parse HEAD
)
```

위 [실행 파일](../../scripts/apply-ops-checkout.sh)은 전용 checkout에 배포 파일 선택 목록을 적용하고 루트의 `.claude`·`.chatgpt`가 사라졌는지 확인합니다. 두 폴더에 Git 미추적 파일이 있으면 해당 폴더를 Git 내부 보관 경로로 이동하고 위치를 출력합니다. 추적 파일에 로컬 변경이 있으면 적용 전에 멈춥니다.

이 디렉터리를 사내 opencode의 작업 루트로 열고 `ops`를 선택합니다. [선택 목록](../../ops-checkout.patterns)은 루트 Makefile, 배포 실행 파일, 운영 에이전트·스킬, 공유 인프라 기록을 포함합니다. 사람용 가이드는 전체 checkout에서 봅니다. 두 checkout의 배포 커밋을 맞추고, Git 밖의 chart·인증서·외부 env는 기존 입력 경로를 지정하거나 앱의 정해진 위치에 준비합니다.

**다음 단계:** [배포 준비와 검증](02-deploy.md#배포-준비)

## Git·운영 파일 관리

checkout·env·인증서·kubeconfig·데이터 위치는
[운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)가 원본입니다.
실제 DB·업무 데이터는 PV/PVC·Worker·외부 저장소에 있어 checkout 복사로 백업되지 않습니다.

### 1. 갱신 전 확인 — 관리 호스트

배포 checkout 루트에서 실행합니다. 모두 조회 명령입니다.

```bash
git status --short
git remote -v
git branch --show-current
git rev-parse HEAD
```

변경 파일이 있으면 내용을 확인하고 보존합니다. 변경을 없애기 위해 강제 초기화하지 않습니다.
원격 저장소와 배포 브랜치가 맞는지 확인합니다.

### 2. 갱신

```bash
git pull --ff-only
git log -1 --oneline
```

**기대 결과:** 배포할 커밋이 표시됩니다. 개발 PC의 미커밋·미추적 파일은 전달되지 않습니다.
Git 갱신은 파일만 바꾸며 Kubernetes 리소스·Secret·DB·실행 중인 Pod를 변경하지 않습니다.

**실패 확인:** fast-forward가 불가능하면 로컬 커밋·변경을 확인하고 담당자와 정리합니다.

`ops` checkout에서는 갱신 후 다음 명령으로 해당 커밋의 파일 선택 목록도 반영합니다.

```bash
./deploy/shared/scripts/apply-ops-checkout.sh
```

### 3. 다음 단계

변경 유형별 검사·적용은 [운영 절차의 업데이트](03-operations.md#업데이트--관리-호스트)를 따릅니다.
