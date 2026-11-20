# Airflow ODBC 파일 넣는 곳

[차트·이미지·ODBC 준비](../docs/02-artifacts.md#3-odbc-설정-준비)

운영에 쓸 `odbc.ini`와 관련 파일을 이 폴더에 넣습니다.
기존 ODBC 폴더를 가져온다면 하위 폴더 구조도 그대로 복사합니다.

실제 설정 파일은 `.gitignore`로 Git 추적에서 제외됩니다.
다른 PC나 서버에서 저장소를 받아도 이 파일들은 내려오지 않으므로 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 관리 호스트의 이 폴더에 따로 둡니다.

배치 예시입니다. 필요한 실제 파일만 넣고 빈 INI나 인증서를 대신 만들지 않습니다.

```text
deploy/airflow/odbc/
├── odbc.ini            # 실제 DSN 설정
├── odbcinst.ini        # 기존 구성에서 사용하는 경우
└── certs/              # 실제 설정에서 참조하는 경우
    └── ca.pem
```

## Worker에 반영

현재 `env/k8s.env`의 `ODBC_HOST_PATH`는 `/appdata/airflow/odbc`입니다.
이 프로젝트 폴더에 파일을 넣는 것만으로 실행 중인 Airflow에 반영되지는 않습니다.
입력 파일을 `NODE_NAME`으로 선택한 Worker(`khinfow01`)에 전달하고 해당 경로에 배치합니다. Worker에서 실행하는 블록은 관리 호스트의 저장소 밖 파일에 저장해 [노드 명령 실행](../../shared/docs/infrastructure/access.md#노드-명령-실행)의 `--script`로 전달합니다.
Worker의 그 경로에 운영 파일이 이미 있고 바꿀 내용이 없으면 3번의 확인만 합니다.

1. [변경] 관리 호스트의 저장소 루트에서 이 폴더의 실제 파일을 tar로 묶습니다. 클러스터와 Worker는 바꾸지 않습니다. `odbc.ini`가 없거나 비어 있으면 묶지 않습니다.

   ```bash
   test -s deploy/airflow/odbc/odbc.ini && (
     umask 077
     tar -C deploy/airflow/odbc --exclude=./README.md --exclude=./.gitignore -cf "$HOME/airflow-odbc.tar" .
     tar -tf "$HOME/airflow-odbc.tar"
   )
   ```

   성공: `./odbc.ini`가 들어 있는 파일 목록이 출력됩니다. 출력이 없으면 `odbc.ini`가 준비되지 않은 것이므로 위의 파일 반입부터 합니다.

2. [변경] `$HOME/airflow-odbc.tar`를 `khinfow01`의 `/tmp/node-exec/airflow-odbc.tar`로 옮긴 뒤 `khinfow01`에서 아래를 실행합니다. 묶음에 비밀번호 같은 비밀값이 없고 64KiB 이하이면 아래 블록을 실행하는 명령에 `--copy "$HOME/airflow-odbc.tar":/tmp/node-exec/airflow-odbc.tar`를 함께 지정하고, 그렇지 않으면 [파일 반입](../../shared/docs/infrastructure/access.md#파일-반입) 절의 방법으로 옮깁니다. 같은 이름의 기존 파일을 덮어쓰므로 기존 폴더를 먼저 tar로 백업하고, 풀어 놓은 파일의 소유자를 Airflow 실행 계정(UID 50000, GID 0)으로 맞춥니다.

   ```bash
   backup="/appdata/airflow/odbc-backup-$(date +%Y%m%d-%H%M%S).tar"
   sudo -n install -d -o 50000 -g 0 -m 0750 /appdata/airflow/odbc
   sudo -n install -o root -g root -m 0600 /dev/null "$backup"
   sudo -n tar -C /appdata/airflow -cf "$backup" odbc
   sudo -n tar -C /appdata/airflow/odbc -xf /tmp/node-exec/airflow-odbc.tar
   sudo -n chown -R 50000:0 /appdata/airflow/odbc
   rm /tmp/node-exec/airflow-odbc.tar
   ```

   복사가 끝나면 관리 호스트의 `$HOME/airflow-odbc.tar`도 지웁니다.

3. [조회] `khinfow01`에서 디렉터리 탐색 권한과 파일 읽기 권한을 확인합니다.

   ```bash
   sudo -n ls -lnR /appdata/airflow/odbc
   ```

   성공: `odbc.ini`와 INI가 참조하는 인증서·하위 파일이 모두 있고 소유자가 `50000 0`입니다. Airflow UID 50000이 INI·인증서와 필요한 모든 하위 파일을 읽을 수 있어야 합니다.

컨테이너에서는 이 폴더 전체를 `/usr/local/odbc`에 읽기 전용으로 연결합니다.
INI 안에서 인증서 등의 절대 경로를 적을 때도 컨테이너 안의 경로를 사용합니다.
예를 들어 위 인증서의 경로는 `/usr/local/odbc/certs/ca.pem`입니다.
`CLOUDERAIMPALAINI`는 별도로 `/etc/cloudera.impalaodbc.ini`를 사용하므로 이 폴더에
같은 이름의 파일을 넣어도 해당 경로의 설정을 덮어쓰지는 않습니다.

파일과 권한을 준비한 뒤 [Airflow 가이드](../README.md#b-업데이트)의 배포를 진행합니다.
