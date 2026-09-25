# 03. 차트·이미지·ODBC 준비

[시작 안내](README.md) · 이전: [환경변수](env/02_ENVIRONMENT.md) · 다음: [단계별 실행](04_SETUP_FLOW.md)

명령은 저장소 루트에서 실행합니다. 이미 배포할 이미지가 registry에 있다면 빌드는 생략하고
선택한 Worker에서 해당 이미지를 가져올 수 있는지 확인합니다.

## 1. 공식 chart 준비

인터넷에 연결된 환경에서는 다음 명령으로 checksum까지 확인합니다.

```bash
python3 deploy/airflow/scripts/manage.py fetch-chart
```

사내망이 외부에 연결되지 않으면 외부 PC에서 받은
`deploy/airflow/helm/vendor/airflow-1.22.0.tgz`를 서버의 같은 위치로 반입합니다.
다른 위치의 파일은 `AIRFLOW_CHART_FILE=/절대경로/airflow-1.22.0.tgz` 환경변수로 지정합니다.
검사·렌더·배포는 차트를 자동 다운로드하지 않으며 고정 SHA-256이 다르면 중단합니다.
차트 dependency도 압축 파일에 포함되어 있어 `helm dependency update`가 필요하지 않습니다.

완료 기준: 고정된 chart 압축 파일이 배포 실행 호스트에 있어야 합니다.
`AIRFLOW_CHART_FILE`을 사용한다면 검사·렌더·배포를 실행하는 같은 셸에서 export합니다.

```bash
read -r -p '반입한 chart의 절대 경로: ' AIRFLOW_CHART_FILE
export AIRFLOW_CHART_FILE
```

## 2. DAG 포함 이미지 준비

`env/build.env`를 사용하면 사내 의존성 이미지의 build arg가 적용됩니다.
사내 base image·APT/PIP mirror·trusted hosts·ODBC artifact URL이 동일하며
`INSTALL_BIGDATAQUERY_PYTHON=true`, `INSTALL_BIGDATAQUERY_ODBC=true`가 기본값입니다.
기존에 공개 기본값으로 만든 `build.env`가 있으면 저장소의 최신 설정과 비교해 이 값을 갱신합니다.
사내 주소는 env에서 변경할 수 있으며 Dockerfile·배포 Python 코드에는 고정하지 않습니다.
빌드 인자에는 비밀번호·접근 토큰을 넣지 않습니다.

```bash
python3 deploy/airflow/scripts/manage.py build-image \
  --build-env deploy/airflow/env/build.env
```

Docker가 있는 빌드 환경에서 실행합니다. 기존 `apps/airflow/image/Dockerfile.dependencies`로 의존성 이미지를 만들고
`apps/airflow/image/Dockerfile`로 DAG·플러그인을 추가합니다. 최종 context는 `apps/airflow`입니다. 빌드 context에 실제 env·로그·DSN은 보내지 않습니다.
이미지는 자동 push하지 않습니다. `k8s.env`에 지정한 이미지 이름으로 `docker push`하거나,
`docker save` 후 서버 containerd에 반입하세요. K3s이면 `sudo k3s ctr images import <이미지.tar>`를 사용합니다.
**Docker에만 이미지가 있어서는 Kubernetes가 사용할 수 없습니다.** PostgreSQL 이미지도 준비합니다.
DAG 변경 시 이미지를 다시 빌드하고 `AIRFLOW_IMAGE_TAG`를 변경해 재배포합니다.
플러그인 소스는 `apps/airflow/plugins`에 두며 최종 이미지에 함께 포함됩니다.

private registry 인증이 필요하면 대상 namespace에 imagePullSecret을 미리 만들고
`IMAGE_PULL_SECRET`에 이름을 입력합니다.

빌드 완료 후 registry로 전달하는 예시입니다. env를 source하지 않고 이미지 이름을 직접 확인해 입력합니다.

```bash
read -r -p 'env와 동일한 repository:tag: ' AIRFLOW_IMAGE_REF
docker image inspect "$AIRFLOW_IMAGE_REF" --format '{{.Id}}'
docker push "$AIRFLOW_IMAGE_REF"
```

registry를 사용하지 않는 경우 위 push 대신 빌드 호스트에서 저장합니다.

```bash
docker save -o /tmp/airflow-image.tar "$AIRFLOW_IMAGE_REF"
```

파일을 선택한 Worker로 전송한 뒤 **해당 Worker에서** 실행합니다. 아래는 K3s 전용 예시이며,
다른 Kubernetes 배포판은 해당 노드의 container runtime 반입 방법을 사용합니다.

```bash
sudo k3s ctr images import /tmp/airflow-image.tar
```

완료 기준: 최종 Airflow 이미지와 PostgreSQL 이미지가 선택한 Worker에서 사용 가능해야 합니다.
빌드 완료만으로 클러스터에 이미지가 전달되지는 않습니다.

## 3. ODBC 설정 준비

ODBC 기본 방식은 기존 디렉터리 전체를 같은 노드에서 읽기 전용으로 마운트하는 방식입니다.
`ODBC_HOST_PATH`를 기존 서버 ODBC 설정 디렉터리의 절대 경로로 지정하면 INI·인증서·하위 파일을 그대로 사용합니다.
새 서버라면 기존 디렉터리 전체를 `/srv/airflow/odbc`로 복사하고 Airflow UID 50000이 읽을 수 있게 권한을 유지합니다.
이 저장소에는 실제 DSN·인증서가 없으므로 빈 파일을 생성해서 대신하지 않습니다.
경로가 없으면 Kubernetes가 Pod 기동을 차단합니다. 단일 서버에 고정하므로 다른 노드의 파일을 참조하지 않습니다.

| 기존 컨테이너 설정 | Kubernetes 유지 값 |
| --- | --- |
| ODBC 디렉터리 | `/usr/local/odbc`, 전체 디렉터리 읽기 전용 |
| `ODBCINI` | `/usr/local/odbc/odbc.ini` |
| `ODBCSYSINI` | `/usr/local/odbc` |
| `CLOUDERAIMPALAINI` | `/etc/cloudera.impalaodbc.ini`, 기존 드라이버 이미지에서 상속 |

Secret 방식을 사용하려면 `ODBC_HOST_PATH=`로 비우고 기존 namespace Secret 이름을
`ODBC_SECRET_NAME`에 지정합니다. 두 방식을 동시에 지정하면 설정 검사에서 중단합니다.
namespace는 `kubectl --context "$AIRFLOW_KUBE_CONTEXT" create namespace airflow`로 미리 만들 수 있습니다.

완료 기준: `ODBC_HOST_PATH`를 사용하면 선택한 Worker에 실제 설정 파일이 있고 UID 50000이 읽을 수 있어야 합니다.
Secret 방식이면 `NAMESPACE`와 동일한 namespace에 참조 Secret이 있어야 합니다.

## 4. 다음 단계

[04 단계별 실행](04_SETUP_FLOW.md)에서 정적 검사 → 클러스터 사전 검사 → 배포 → 접속 확인을 수행합니다.
