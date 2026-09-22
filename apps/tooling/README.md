# 저장소 도구

앱 소스와 배포 파일을 검사하는 개발·CI 도구입니다. 배포 서비스가 아니므로 서버 앱 목록이나 선택 checkout에 포함하지 않습니다.

| 위치 | 역할 |
| --- | --- |
| `agent/` | 앱 구조·frontend/backend 경계·UI·문서 감사 |
| `agent/tests/` | 감사 도구 단위 테스트 |
| `tests/` | Compose·서버 checkout·배포 도구 회귀 테스트 |

구조 검사는 `deploy/shared/apps.json`과 apps·deploy·local의 소유 디렉터리를 대조합니다.
tooling·shared·로컬 mock은 서비스 목록 밖의 지원 영역이며 runtime·chart·Node 생성물은 앱으로 취급하지 않습니다.
로컬 배포 회귀 검사는 앱별 독립 렌더와 전체 집계의 리소스·권한·realm 참조를 확인합니다.

저장소 루트에서 실행합니다.

```bash
make audit
node --test apps/tooling/tests/*.test.cjs
make compose-check
```

배포 회귀 테스트는 Docker Compose·kubectl이 필요하며 실제 클러스터를 변경하지 않습니다.
Helm이 준비되어 있으면 고정 chart 렌더 검사도 수행합니다. 기존 `.tools/bin/helm`을 사용하려면 PATH에 추가합니다.
앱 실행은 루트 Makefile, [사용 안내](../../docs/usage.md), [개발 환경](../../local/README.md)을 참고합니다.

Node 의존성은 이 폴더의 package.json·lockfile로 관리합니다. 루트에서 `make tooling-install` 후 `make tooling-test`를 사용합니다. Web 설치나 루트 node_modules에 의존하지 않습니다.

Feature Guardrails CI의 별도 tooling 작업에서도 `make tooling-test`를 실행합니다.
