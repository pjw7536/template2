# Airflow 2.11.0 + code-server 포함 커스텀 이미지
FROM apache/airflow:2.11.0

USER root

# code-server 버전은 필요 시 변경 가능
ARG CODE_SERVER_VERSION=4.105.1

# code-server 설치 (공식 릴리스 tar 사용)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates; \
    curl -fsSL "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server-${CODE_SERVER_VERSION}-linux-amd64.tar.gz" \
      | tar -xz -C /usr/local --strip-components=1 code-server-${CODE_SERVER_VERSION}-linux-amd64; \
    ln -sf /usr/local/bin/code-server /usr/bin/code-server; \
    apt-get purge -y --auto-remove curl; \
    rm -rf /var/lib/apt/lists/*

# airflow 유저 홈/설정 디렉터리 사전 생성
RUN mkdir -p \
      /home/airflow/.config/code-server \
      /home/airflow/.local/share/code-server \
      /home/airflow/.local/share/code-server/extensions \
      /home/airflow/.vscode \
    && chown -R 50000:0 /home/airflow

# 기본 유저 되돌리기
USER airflow

WORKDIR /opt/airflow

