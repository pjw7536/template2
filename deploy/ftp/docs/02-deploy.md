# FTP 검사·배포·접속 확인

[앱 안내](../README.md) · [전체 배포 안내](../../README.md)

**실행 위치:** 관리 호스트의 저장소 루트입니다. [서버 준비](01-setup.md)의 도구·디스크·계정과 실행 입력을 먼저 준비합니다. 새 터미널에서는 준비 문서의 context와 env 입력을 다시 설정합니다.

## 5. 검사 후 배포

관리 호스트의 저장소 루트로 돌아옵니다. 앞서 export한 세 변수를 사용합니다.
실행기는 [env/prod.env](../env/prod.env)을 자동으로 읽어 `FTP_IMAGE`의 사내 Docker Hub 미러 이미지를 적용합니다.
기존 공개 이미지 digest를 유지한 선언이며, 사내 미러의 해당 digest 제공 여부·접근·CA는 Worker에서 확인합니다.
다른 경로 또는 digest가 필요하면 이 env의 `FTP_IMAGE`를 실제 주소로 바꿉니다. `http://`, `https://`는 붙이지 않습니다.
registry 인증이 필요하면 `etch-ftp` namespace에 pull Secret을 미리 준비하고 같은 env의 `IMAGE_PULL_SECRET`에 이름을 입력합니다.
빈 값이면 pull Secret을 추가하지 않습니다. FTP 로그인용 계정 파일과 이미지 설정 env는 별개입니다.
별도 env는 `export FTP_ENV=/절대/경로/ftp.env`로 지정합니다. 별도 overlay 운영은 [수동 배포](04-kubernetes.md)를 사용합니다.

```bash
make server-check APP=ftp PROFILE=prod
make ftp-check

# 위 검사가 통과하고 출력된 context·노드·IP가 맞으면 실행합니다.
make ftp-up
```

| 명령 | 처리 내용 |
| --- | --- |
| `ftp-check` | 이미지 설정·선택 pull Secret 존재, 계정 형식·권한, 원본 렌더, 대상 노드 상태, 기존 Secret 일치 여부 검사 |
| `ftp-up` | 같은 검사 → namespace 준비 → 없는 Secret 생성 → 노드 라벨 → 스택 적용 → 최대 5분 기동 대기 → Pod 위치 출력 |

기존 Secret이 입력과 다르면 변경 전에 중단합니다. 동일 입력으로 재실행할 수 있고 파일 데이터를 삭제하지 않습니다.
배포 중 실패하면 이미 적용된 리소스는 남습니다. 원인을 해결하고 같은 입력으로 재실행합니다.

스크립트는 `deploy/ftp/scripts/up.py`이며 Python 표준 라이브러리만 사용합니다.
모든 클러스터 명령은 명시한 context를 사용합니다.

이 실행기는 `k8s/` 공통 원본에 운영 env의 이미지·pull Secret을 반영합니다.
`kubectl apply -k deploy/ftp/k8s`를 직접 실행하면 env가 적용되지 않고 공개 이미지를 사용합니다.
다른 저장 경로나 추가 패치가 필요하면 [수동 배포·overlay 절차](04-kubernetes.md)를 사용합니다.

검사 통과는 이미지 pull·원격 디스크·방화벽·실제 FTP 인증 성공을 보장하지 않습니다.

## 6. 완료 확인

[접속 확인과 운영](03-operations.md)의 업로드·다운로드 검증까지 수행하면 설치가 완료됩니다.
각 Worker마다 Pod의 `NODE`, 실제 접속 IP, 업로드 후 호스트 파일 위치를 확인합니다.
다른 노드의 저장 폴더에 테스트 파일이 생기지 않는 것도 확인합니다.
현재 구성은 IPv4 직접 접속과 passive 모드용이며 Service·Ingress·VIP를 만들지 않습니다.
TLS나 NAT 주소를 자동 설정하지 않습니다.

검증 후에는 [서비스 기록](../../shared/docs/infrastructure/services.md#ftp-노드별-파일-수신)에 대상 노드·접속 주소·검증 결과를,
[네트워크 기록](../../shared/docs/infrastructure/network.md#ftp-직접-접속)을 실제 방화벽 확인 결과와 함께 갱신합니다.
