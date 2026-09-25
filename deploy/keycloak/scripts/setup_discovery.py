#!/usr/bin/env python3
"""Discovery를 검증하고 기존 Keycloak 설정 Job을 순서대로 실행합니다."""

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "deploy/shared/scripts"
BASE = ROOT / "deploy/keycloak"
ENDPOINTS = {
    "authorization_endpoint": "CORP_OIDC_AUTH_URL",
    "token_endpoint": "CORP_OIDC_TOKEN_URL",
    "issuer": "CORP_OIDC_ISSUER",
    "jwks_uri": "CORP_OIDC_JWKS_URL",
    "userinfo_endpoint": "CORP_OIDC_USERINFO_URL",
    "end_session_endpoint": "CORP_OIDC_LOGOUT_URL",
}


def read_env(path):
    """기존 dotenv처럼 값을 실행하지 않고 데이터로 읽습니다."""
    values = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*=", line):
            raise ValueError(f"env 형식 오류: {number}행")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"env 중복 항목: {key}")
        values[key] = value
    return values


def https_url(value, label):
    """Credential·제어문자 없는 HTTPS URL만 허용합니다."""
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value):
        raise ValueError(f"HTTPS URL 형식 오류: {label}")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"HTTPS URL 형식 오류: {label}")
    return value


def resolve_metadata(values, metadata):
    """Metadata를 기존 IdP Job 입력으로 변환하며 credential은 그대로 유지합니다."""
    if not isinstance(metadata, dict):
        raise ValueError("discovery 응답은 JSON 객체여야 합니다.")
    result = dict(values)
    for claim, key in ENDPOINTS.items():
        value = metadata.get(claim)
        if not value:
            if claim in ("userinfo_endpoint", "end_session_endpoint"):
                # Discovery에 없는 선택 endpoint는 명시적인 env 입력으로 보완할 수 있습니다.
                value = values.get(key, "")
                if not value:
                    result[key] = ""
                    continue
            else:
                raise ValueError(f"discovery 필수 항목 누락: {claim}")
        if claim == "issuer":
            # AD FS의 issuer는 HTTP 식별자일 수 있으며 이 주소로 통신하지 않습니다.
            checked = value.replace("http://", "https://", 1) if isinstance(value, str) and value.startswith("http://") else value
            https_url(checked, claim)
            result[key] = value
        else:
            result[key] = https_url(value, claim)
    method = values.get("CORP_OIDC_CLIENT_AUTH_METHOD")
    if not method:
        raise ValueError("필수 설정 누락: CORP_OIDC_CLIENT_AUTH_METHOD")
    methods = metadata.get("token_endpoint_auth_methods_supported", ["client_secret_basic"])
    if not isinstance(methods, list) or method not in methods:
        raise ValueError("발급받은 client 인증 방식이 discovery 지원 목록과 다릅니다.")
    response_types = metadata.get("response_types_supported", [])
    if not isinstance(response_types, list) or "code" not in response_types:
        raise ValueError("discovery가 Authorization Code 응답을 지원하지 않습니다.")
    scopes = metadata.get("scopes_supported", ["openid"])
    if not isinstance(scopes, list) or "openid" not in scopes:
        raise ValueError("discovery가 openid scope를 지원하지 않습니다.")
    if values.get("CORP_OIDC_VALIDATE_SIGNATURE", "true") != "true":
        raise ValueError("discovery 설정 흐름에는 CORP_OIDC_VALIDATE_SIGNATURE=true가 필요합니다.")
    result["CORP_OIDC_VALIDATE_SIGNATURE"] = "true"
    return result


def discover(values):
    """실행 호스트의 신뢰 저장소로 TLS를 검증해 metadata만 조회합니다."""
    required = ("CORP_OIDC_DISCOVERY_URL", "CORP_OIDC_CLIENT_ID", "CORP_OIDC_CLIENT_SECRET", "CORP_OIDC_CLIENT_AUTH_METHOD")
    missing = [key for key in required if not values.get(key, "").strip()]
    if missing:
        raise ValueError("필수 설정 누락: " + ", ".join(missing))
    placeholders = [key for key in required if any(marker in values[key] for marker in ("<", "example.invalid", "replace-me", "change-me"))]
    if placeholders:
        raise ValueError("실제 값으로 교체할 설정: " + ", ".join(placeholders))
    if values["CORP_OIDC_CLIENT_AUTH_METHOD"] not in ("client_secret_basic", "client_secret_post"):
        raise ValueError("CORP_OIDC_CLIENT_AUTH_METHOD: client_secret_basic 또는 client_secret_post 필요")
    url = https_url(values.get("CORP_OIDC_DISCOVERY_URL", ""), "CORP_OIDC_DISCOVERY_URL")
    with urlopen(url, timeout=30) as response:
        https_url(response.geturl(), "discovery 최종 URL")
        content = response.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError("discovery 응답이 1 MiB를 초과합니다.")
    return resolve_metadata(values, json.loads(content))


def write_resolved(path, values):
    """공통 env 도구가 재조회하지 않도록 해석된 입력만 비공개 파일에 저장합니다."""
    with open(path, "w", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
        os.fchmod(output.fileno(), 0o600)
        output.write("".join(f"{key}={value}\n" for key, value in values.items()
                             if key.startswith("CORP_OIDC_") and key != "CORP_OIDC_DISCOVERY_URL"))


def run(args, **kwargs):
    """Credential이 포함될 수 있는 외부 명령 출력은 오류 원문까지 숨깁니다."""
    result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise ValueError("외부 명령 실패: 현재 단계의 입력·접속·Job 상태를 확인하세요.")
    return result.stdout


def setup(action, context, env_path, portal_env=None):
    """모든 입력을 검사한 뒤 요청된 경우에만 클러스터에 적용합니다."""
    print("사전 검사: discovery 및 발급 입력", flush=True)
    values = discover(read_env(env_path))
    kube = ["kubectl", "--context", context, "-n", "etch-sso"]
    with tempfile.TemporaryDirectory(prefix="keycloak-discovery-") as directory:
        temporary = Path(directory)
        resolved = temporary / "resolved.env"
        write_resolved(resolved, values)
        run(["bash", SHARED / "check-env.sh", "keycloak", "prod", "oidc", resolved])
        if portal_env:
            run(["bash", SHARED / "check-env.sh", "portal", "prod", "client", portal_env])
        # 서버 소스만 선택 checkout한 환경에서도 적용 전에 필요한 파일을 확인합니다.
        files = [BASE / "k8s/claims/sync-oidc-claim-mappers.sh", BASE / "k8s/claims/account-user-profile.json",
                 BASE / "k8s/oidc/admin-common.sh", BASE / "k8s/oidc/setup-oidc.sh"]
        for path in files + [BASE / "k8s/oidc/oidc-setup-job.yaml", BASE / "k8s/claims/claim-mappers-job.yaml"]:
            if not path.is_file():
                raise ValueError(f"설정 파일 누락: {path.relative_to(ROOT)}")
        if portal_env:
            run(["kubectl", "kustomize", ROOT / "deploy/portal/k8s/jobs/keycloak-client"])
        print("사전 검사 통과. Discovery endpoint와 기존 claim 계약을 사용합니다.", flush=True)
        if action == "check":
            return
        # 공통 Secret 도구에도 같은 context를 강제합니다. 현재 context는 변경하지 않습니다.
        wrapper = temporary / "kubectl"
        wrapper.write_text(f"#!/bin/sh\nexec kubectl --context {shlex.quote(context)} \"$@\"\n")
        wrapper.chmod(0o700)
        command_env = {**os.environ, "KUBECTL_BIN": str(wrapper)}
        print("적용: OIDC Secret 및 관리 ConfigMap", flush=True)
        run(["bash", SHARED / "apply-env.sh", "keycloak", "prod", "oidc", resolved], env=command_env)
        config = run(kube + ["create", "configmap", "keycloak-claim-mapper",
                            *[f"--from-file={path}" for path in files], "--dry-run=client", "-o", "json"])
        run(kube + ["apply", "-f", "-"], input=config)

        def job(name, manifest, kustomize=False):
            print(f"적용 및 완료 대기: {name}", flush=True)
            run(kube + ["delete", "job", name, "--ignore-not-found", "--wait=true"])
            run(kube + ["apply", "-k" if kustomize else "-f", manifest])
            run(kube + ["wait", "--for=condition=complete", f"job/{name}", "--timeout=15m"])

        job("keycloak-oidc-setup", BASE / "k8s/oidc/oidc-setup-job.yaml")
        job("keycloak-oidc-claim-mappers", BASE / "k8s/claims/claim-mappers-job.yaml")
        if portal_env:
            print("적용: Portal client Secret", flush=True)
            run(["bash", SHARED / "apply-env.sh", "portal", "prod", "client", portal_env], env=command_env)
            job("portal-keycloak-client", ROOT / "deploy/portal/k8s/jobs/keycloak-client", True)
    print("설정 완료. 시험 계정으로 사내 로그인과 발급 claim을 확인하세요.", flush=True)


def main():
    """사전 검사와 실제 적용의 명령 진입점입니다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply", "resolve"))
    parser.add_argument("--context")
    parser.add_argument("--env", type=Path, default=BASE / "env/prod.env")
    parser.add_argument("--portal-env", type=Path)
    parser.add_argument("--output", type=Path, help="resolve 전용 임시 env 출력 파일")
    args = parser.parse_args()
    if args.action == "resolve" and not args.output:
        parser.error("resolve에는 --output이 필요합니다.")
    if args.action != "resolve" and not (args.context or "").strip():
        parser.error("--context는 비어 있을 수 없습니다.")
    try:
        if args.action == "resolve":
            write_resolved(args.output, discover(read_env(args.env)))
        else:
            setup(args.action, args.context, args.env, args.portal_env)
    except (ValueError, OSError) as error:
        # URL·credential이 담길 수 있는 네트워크 예외 원문은 출력하지 않습니다.
        message = str(error) if type(error) is ValueError else "입력 파일 또는 discovery 접속/JSON 처리가 실패했습니다."
        parser.exit(1, f"설정 중단: {message}\n")


if __name__ == "__main__":
    main()
