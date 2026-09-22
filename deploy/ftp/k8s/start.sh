#!/usr/bin/env bash
set -euo pipefail

# 계정과 노드 주소가 없으면 이미지의 기본 계정으로 실행하지 않습니다.
: "${FTP_USER:?FTP_USER가 필요합니다.}"
: "${FTP_PASS:?FTP_PASS가 필요합니다.}"
: "${PASV_ADDRESS:?노드 IP가 필요합니다.}"
[[ "$FTP_USER" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'FTP_USER 형식이 잘못되었습니다.' >&2; exit 1; }
[[ "$FTP_PASS" != *$'\n'* && "$FTP_PASS" != *$'\r'* && "$FTP_PASS" != *\\* ]] || {
  echo 'FTP_PASS에는 줄바꿈과 역슬래시를 사용할 수 없습니다.' >&2; exit 1;
}

# 기존 접속 포트와 로그인 후 data_movement 경로를 유지합니다.
sed -i '/^listen_port=/d; /^local_root=/d; /^port_enable=/d' /etc/vsftpd/vsftpd.conf
cat >> /etc/vsftpd/vsftpd.conf <<'EOF'
listen_port=6380
local_root=/data
port_enable=NO
EOF
# 기존 하위 파일의 소유권은 바꾸지 않습니다.
chown ftp:ftp /data/data_movement
exec /usr/sbin/run-vsftpd.sh
