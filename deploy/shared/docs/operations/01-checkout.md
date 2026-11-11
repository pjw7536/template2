# 서버 파일 받기

[공통 안내](../README.md) · 다음: [배포 준비와 검증](02-deploy.md)

CP1에 저장소를 clone하고 Git으로 갱신하는 방법입니다. CP1은 저장소 전체를 사용합니다([운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)).

- [저장소 clone](#저장소-clone)
- [Git·운영 파일 관리](#git운영-파일-관리)

## 저장소 clone

### 1. 준비물과 실행 위치

| 항목 | 내용 |
| --- | --- |
| 실행 위치 | CP1(관리 호스트). 앱 Pod와 데이터가 놓이는 Worker는 앱별 배포 정의가 정합니다 |
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

**다음 단계:** [배포 준비와 검증](02-deploy.md#배포-준비)

## Git·운영 파일 관리

checkout·env·인증서·kubeconfig·데이터 위치는
[운영 파일 위치](../infrastructure/operations.md#운영-파일과-데이터-위치)가 원본입니다.
실제 DB·업무 데이터는 PV/PVC·Worker·외부 저장소에 있어 checkout 복사로 백업되지 않습니다.

### 1. 갱신 전 확인 — CP1

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

### 3. 다음 단계

변경 유형별 검사·적용은 [운영 절차의 업데이트](03-operations.md#업데이트--cp1)를 따릅니다.
