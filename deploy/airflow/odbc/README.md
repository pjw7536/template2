# Airflow ODBC 파일 넣는 곳

[차트·이미지·ODBC 준비](../03_ARTIFACTS.md#3-odbc-설정-준비)

이 폴더에 운영에 사용하는 `odbc.ini`와 관련 파일을 넣습니다.
기존 ODBC 디렉터리가 있다면 하위 폴더 구조를 유지해서 복사합니다.
실제 입력 파일은 이 폴더의 `.gitignore`로 Git 추적에서 제외됩니다.
따라서 다른 PC나 서버에서 checkout해도 입력 파일은 내려오지 않으며 별도로 전달해야 합니다.

배치 예시입니다. 필요한 실제 파일만 넣고 빈 INI나 인증서를 대신 만들지 않습니다.

```text
deploy/airflow/odbc/
├── odbc.ini            # 실제 DSN 설정
├── odbcinst.ini        # 기존 구성에서 사용하는 경우
└── certs/              # 실제 설정에서 참조하는 경우
    └── ca.pem
```

## Worker에 반영

현재 `env/k8s.env`의 `ODBC_HOST_PATH`는 `/srv/airflow/odbc`입니다.
이 프로젝트 폴더에 파일을 넣는 것만으로 실행 중인 Airflow에 반영되지는 않습니다.
입력 파일을 `NODE_NAME`으로 선택한 Worker에 전달하고 해당 경로에 배치합니다.

저장소가 해당 Worker에 있고 파일을 채워 두었다면, 저장소 루트에서 실행합니다.
아래 명령은 같은 이름의 기존 파일을 덮어쓰므로 운영 파일은 먼저 백업합니다.

```bash
test -s deploy/airflow/odbc/odbc.ini && (
  set -euo pipefail
  sudo install -d -o 50000 -g 0 -m 0750 /srv/airflow/odbc
  sudo tar -C deploy/airflow/odbc --exclude=./README.md --exclude=./.gitignore -cf - . |
    sudo tar -C /srv/airflow/odbc -xf -
)
```

복사 후 디렉터리 탐색 권한과 파일 읽기 권한을 확인합니다. Airflow UID 50000이
INI·인증서와 필요한 모든 하위 파일을 읽을 수 있어야 합니다.
다른 실행 호스트에 저장소가 있다면 실제 파일을 Worker로 먼저 전송하고 같은 기준으로 배치합니다.

컨테이너에서는 이 디렉터리 전체가 `/usr/local/odbc`에 읽기 전용으로 마운트됩니다.
INI에서 인증서 등을 절대 경로로 참조한다면 컨테이너 경로를 사용합니다.
위 예시의 인증서는 `/usr/local/odbc/certs/ca.pem`으로 접근합니다.
`CLOUDERAIMPALAINI`는 별도로 `/etc/cloudera.impalaodbc.ini`를 사용하므로 이 폴더에
같은 이름의 파일을 넣어도 해당 경로의 설정을 덮어쓰지는 않습니다.

파일과 권한을 준비한 뒤 [단계별 검사·배포](../04_SETUP_FLOW.md)를 진행합니다.
