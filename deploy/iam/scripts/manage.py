#!/usr/bin/env python3
"""IAM의 운영 이미지를 게시하고 Keycloak 설정과 Kubernetes 워크로드를 배포합니다."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
from urllib.parse import quote, urlsplit

from setup_keycloak import CLIENT_ID, SetupError, check_public_url, read_env

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
SHARED = APP.parent / "shared"
sys.path.insert(0, str(SHARED / "scripts"))
import ca_bundle  # noqa: E402
import image_registry  # noqa: E402
from runtime import is_placeholder, module  # noqa: E402

tls = module("iam_tls", SHARED / "ingress/tls.py")
routing = module("iam_routing", SHARED / "ingress/routing.py")
host_dirs = module("iam_host_dirs", SHARED / "scripts/host_dirs.py")
NAMESPACE = "iam"
VOLUME = "iam-workload-data"
COMPONENTS = ("api", "web")
BUILD_KEYS = {"NODE_BASE_IMAGE", "NGINX_BASE_IMAGE", "PYTHON_BASE_IMAGE", "NPM_REGISTRY", "PIP_INDEX_URL", "PIP_TRUSTED_HOST"}
DNS_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"


def run(args, data=None):
    """명령 실패 원인을 전달하고 민감한 표준 입력은 출력하지 않습니다."""
    result = subprocess.run(list(map(str, args)), input=data, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"{args[0]} 명령이 실패했습니다.")
    return result.stdout


def iam_settings(env):
    values = read_env(env)
    origin = check_public_url(values.get("IAM_PUBLIC_URL", ""))
    host = urlsplit(origin).hostname
    if origin != f"https://{host}" or not re.fullmatch(rf"{DNS_LABEL}(?:\.{DNS_LABEL})+", host):
        raise ValueError("IAM_PUBLIC_URL에는 포트·경로가 없는 운영 HTTPS 주소가 필요합니다.")
    node = values.get("IAM_STORAGE_NODE", "")
    if not re.fullmatch(rf"{DNS_LABEL}(?:\.{DNS_LABEL})*", node) or len(node) > 253:
        raise ValueError("IAM_STORAGE_NODE에는 업무 부하 데이터를 보관할 Worker의 hostname label이 필요합니다.")
    path = values.get("IAM_DATA_HOST_PATH", "")
    if not re.fullmatch(r"/appdata/[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)*", path):
        raise ValueError("IAM_DATA_HOST_PATH는 /appdata 아래의 IAM 전용 디렉터리여야 합니다.")
    realm = values.get("KEYCLOAK_TARGET_REALM") or "etch"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", realm) or realm.lower() in {"master", ".", ".."}:
        raise ValueError("KEYCLOAK_TARGET_REALM에 업무 realm을 지정하세요.")
    return {"origin": origin, "host": host, "node": node, "path": path, "realm": realm}


def build_settings(path):
    values = read_env(path)
    missing = sorted(key for key in BUILD_KEYS if not values.get(key) or is_placeholder(values[key]))
    if missing:
        raise ValueError("IAM 이미지 빌드 입력을 확인하세요. " + ", ".join(missing))
    return values


def image_refs(build_env, registry_env):
    """이미지 게시와 배포·대조가 같은 이미지 이름과 소스 tag를 씁니다."""
    host = read_env(registry_env).get("REGISTRY_HOST", "")
    if len(host) > 253 or not re.fullmatch(rf"{DNS_LABEL}(?:\.{DNS_LABEL})+", host):
        raise ValueError("REGISTRY_ENV의 REGISTRY_HOST에 Zot 공개 host를 설정하세요.")
    images = {}
    for component in COMPONENTS:
        tag = image_registry.source_tag(ROOT, [f"apps/iam/{component}"], [build_env])
        images[component] = f"{host}/tailwind/iam-{component}:{tag}"
    return images


def publish(build_env, registry_env, push_env):
    build_args = build_settings(build_env)
    cadata = ca_bundle.bundle_text() or None
    command = None
    for component, reference in image_refs(build_env, registry_env).items():
        if image_registry.remote_exists(reference, cadata):
            print(f"Zot에 이미 있는 tag를 사용합니다. {reference}", flush=True)
            continue
        command = command or image_registry.nerdctl()
        source = ROOT / "apps/iam" / component
        declared = image_registry.declared_args(source / "Dockerfile")
        print(f"IAM 이미지 빌드: {reference}", flush=True)
        image_registry.build(run, command, reference, source,
                             build_args={key: build_args[key] for key in sorted(declared)})
        image_registry.push(run, command, reference, push_env)
        print(f"IAM 이미지 push 완료: {reference}", flush=True)


def keycloak_tls(env):
    url = check_public_url(read_env(env).get("keycloak-public-url", ""))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not re.fullmatch(rf"{DNS_LABEL}(?:\.{DNS_LABEL})+", parsed.hostname):
        raise ValueError("KEYCLOAK_ENV의 keycloak-public-url에 Keycloak의 공개 HTTPS 주소를 지정하세요.")
    path = Path(os.environ.get("KEYCLOAK_CA_FILE") or ca_bundle.bundle_path(parsed.hostname))
    data = path.read_text() if path.is_file() else ""
    if not data:
        raise ValueError("Keycloak CA 묶음이 없습니다. 사내 CA를 배치하고 공용 CA 준비 검사를 실행하세요.")
    ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(cadata=data)
    return url, data


def config_map(name, data):
    return {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name, "namespace": NAMESPACE}, "data": data}


def manifests(settings, keycloak_url, ca, images):
    """사용자 토큰이나 관리자 계정 없이 필요한 공개 설정과 CA만 렌더합니다."""
    stack = json.loads((APP / "k8s/stack.json").read_text())["items"]
    web_config = {"keycloakUrl": keycloak_url, "realm": settings["realm"], "clientId": CLIENT_ID}
    web_data = "window.__IAM_CONFIG__ = " + json.dumps(web_config, ensure_ascii=True) + ";\n"
    config = [config_map("iam-web-config", {"config.js": web_data}), config_map("iam-keycloak-ca", {"ca.crt": ca})]
    for item in stack:
        if item["kind"] == "Ingress":
            item["spec"]["rules"][0]["host"] = settings["host"]
        elif item["kind"] == "PersistentVolume":
            spec = item["spec"]
            spec["local"]["path"] = settings["path"]
            spec["nodeAffinity"]["required"]["nodeSelectorTerms"][0]["matchExpressions"][0]["values"] = [settings["node"]]
        elif item["kind"] == "Deployment":
            template = item["spec"]["template"]
            pod = template["spec"]
            container = pod["containers"][0]
            component = container["name"]
            container["image"] = images[component]
            source = web_data if component == "web" else ca
            template["metadata"]["annotations"] = {"deploy.tailwind.local/config-sha256": hashlib.sha256(source.encode()).hexdigest()}
            if component == "api":
                pod["nodeSelector"] = {"kubernetes.io/hostname": settings["node"]}
                issuer = next(value for value in container["env"] if value["name"] == "IAM_KEYCLOAK_ISSUER")
                issuer["value"] = f"{keycloak_url}/realms/{quote(settings['realm'], safe='')}"
    # Namespace 다음에 ConfigMap을 만들어 참조 리소스보다 먼저 배포합니다.
    return [stack[0], *config, *stack[1:]]


def manifest_text(items):
    return json.dumps({"apiVersion": "v1", "kind": "List", "items": items}, ensure_ascii=False)


def get(kube, *args):
    output = run([*kube, "get", *args, "-o", "json"])
    return json.loads(output) if output.strip() else None


def check_node(kube, name):
    nodes = get(kube, "nodes", "-l", f"kubernetes.io/hostname={name}")["items"]
    if len(nodes) != 1:
        raise ValueError("IAM_STORAGE_NODE와 일치하는 노드가 정확히 하나 있어야 합니다.")
    node = nodes[0]
    labels, spec, status = node["metadata"].get("labels", {}), node["spec"], node["status"]
    if ("node-role.kubernetes.io/control-plane" in labels or "node-role.kubernetes.io/master" in labels
            or spec.get("unschedulable")
            or not any(c["type"] == "Ready" and c["status"] == "True" for c in status.get("conditions", []))
            or any(t["effect"] in ("NoSchedule", "NoExecute") for t in spec.get("taints", []))):
        raise ValueError("IAM_STORAGE_NODE에 Ready 상태이며 일반 Pod를 받을 수 있는 Worker를 지정하세요.")


def needs_volume(kube, volume, claim, namespace_exists):
    """기존 SQLite가 다른 경로·노드·PVC에 연결된 경우 기존 데이터를 보호합니다."""
    current = get(kube, "pv", VOLUME, "--ignore-not-found")
    pvc = get(kube, "pvc", VOLUME, "-n", NAMESPACE, "--ignore-not-found") if namespace_exists else None
    if pvc:
        desired_claim = claim["spec"]
        spec = pvc["spec"]
        if (pvc["metadata"].get("deletionTimestamp")
                or any(spec.get(key, "") != desired_claim[key] for key in ("volumeName", "accessModes", "storageClassName", "volumeMode", "resources"))):
            raise ValueError("기존 IAM PVC의 예약 볼륨·용량·저장소 설정이 운영 원본과 다릅니다.")
    if not current:
        if pvc:
            raise ValueError("기존 IAM PVC의 PV가 없습니다. 업무 부하 데이터를 확인한 뒤 PV를 복구하세요.")
        return True
    wanted = volume["spec"]
    spec = current["spec"]
    reference = spec.get("claimRef", {})
    if (current["metadata"].get("deletionTimestamp") or current.get("status", {}).get("phase") in ("Released", "Failed")
            or any(spec.get(key, "") != wanted[key]
                   for key in ("local", "nodeAffinity", "capacity", "persistentVolumeReclaimPolicy", "storageClassName", "volumeMode", "accessModes"))
            or any(reference.get(key) != wanted["claimRef"][key] for key in ("name", "namespace"))
            or reference.get("uid") and reference["uid"] != (pvc or {}).get("metadata", {}).get("uid")):
        raise ValueError("기존 IAM PV의 경로·노드·PVC·보존 정책이 다릅니다. 운영 입력과 기존 데이터를 확인하세요.")
    return False


def route_plan(kube, host):
    current = get(kube, "deployment", "traefik", "-n", "etch-sso")
    tls.check(kube, host, current)
    for item in get(kube, "ingresses", "-A")["items"]:
        metadata = item["metadata"]
        if ((metadata["namespace"], metadata["name"]) != (NAMESPACE, "iam")
                and any(rule.get("host") == host for rule in item["spec"].get("rules", []))):
            raise ValueError(f"{host}는 다른 Ingress에서 사용 중입니다. {metadata['namespace']}/{metadata['name']}")
    return routing.namespace_access(NAMESPACE, current), routing.namespace_patch(current, NAMESPACE)


def keycloak_setup(env, keycloak_env, settings, apply=False):
    args = [sys.executable, APP.parent / "keycloak/scripts/admin_env.py", "--env", keycloak_env, "--",
            sys.executable, APP / "scripts/setup_keycloak.py", "--env", env,
            "--public-url", settings["origin"], "--realm", settings["realm"]]
    print(run(args + (["--apply"] if apply else [])).strip(), flush=True)


def deploy(context, env, keycloak_env, settings, items, images, check_only=False):
    kube = ["kubectl", "--context", context]
    scoped = [*kube, "-n", NAMESPACE]
    check_node(kube, settings["node"])
    access, _ = route_plan(kube, settings["host"])
    namespace, = [item for item in items if item["kind"] == "Namespace"]
    volume, = [item for item in items if item["kind"] == "PersistentVolume"]
    claim, = [item for item in items if item["kind"] == "PersistentVolumeClaim"]
    ingress, = [item for item in items if item["kind"] == "Ingress"]
    workload = [item for item in items if item["kind"] not in ("Namespace", "PersistentVolume", "Ingress")]
    namespace_exists = bool(get(kube, "namespace", NAMESPACE, "--ignore-not-found"))
    provision = needs_volume(kube, volume, claim, namespace_exists)
    if provision:
        run([*kube, "create", "--dry-run=server", "-f", "-"], data=json.dumps(volume))
    if namespace_exists:
        run([*kube, "apply", "--dry-run=server", "-f", "-"], data=manifest_text([*access, *workload, ingress]))
    if check_only:
        keycloak_setup(env, keycloak_env, settings)
        print("IAM 입력·노드·저장소·라우팅·Keycloak 검사 통과.")
        return
    for reference in images.values():
        if not image_registry.remote_exists(reference, ca_bundle.bundle_text() or None):
            raise ValueError(f"Zot에 IAM 이미지가 없습니다. make iam-image를 먼저 실행하세요. {reference}")
    if not namespace_exists:
        run([*kube, "apply", "-f", "-"], data=json.dumps(namespace))
        run([*kube, "apply", "--dry-run=server", "-f", "-"], data=manifest_text([*access, *workload, ingress]))
    if provision:
        host_dirs.prepare(run, kube, "iam-storage-prepare", NAMESPACE, settings["node"], images["api"],
                          [(settings["path"], 10001, 10001, "0700")])
        run([*kube, "create", "-f", "-"], data=json.dumps(volume))
    keycloak_setup(env, keycloak_env, settings, apply=True)
    run([*kube, "apply", "-f", "-"], data=manifest_text(workload))
    for component in COMPONENTS:
        run([*scoped, "rollout", "status", f"deployment/iam-{component}", "--timeout=300s"])
    # 워크로드가 준비되는 동안 바뀐 Traefik 설정을 적용 직전에 다시 읽습니다.
    access, patch = route_plan(kube, settings["host"])
    run([*kube, "apply", "-f", "-"], data=manifest_text(access))
    if patch:
        run([*kube, "-n", "etch-sso", "patch", "deployment", "traefik", "--type=json", "--patch", json.dumps(patch)])
        run([*kube, "-n", "etch-sso", "rollout", "status", "deployment/traefik", "--timeout=300s"])
    run([*kube, "apply", "-f", "-"], data=json.dumps(ingress))
    print(f"IAM 웹·업무 부하 API 배포 완료: {settings['origin']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("static", "publish", "check", "deploy", "render"))
    parser.add_argument("--context", default="")
    parser.add_argument("--env", type=Path, default=APP / "env/prod.env")
    parser.add_argument("--build-env", type=Path, default=APP / "env/build.env")
    parser.add_argument("--keycloak-env", type=Path, default=APP.parent / "keycloak/env/prod.env")
    parser.add_argument("--registry-env", type=Path, default=APP.parent / "registry/env/k8s.env")
    parser.add_argument("--push-env", type=Path, default=APP.parent / "registry/env/push-initial.env")
    args = parser.parse_args()
    if args.action == "publish":
        publish(args.build_env, args.registry_env, args.push_env)
        return
    settings = iam_settings(args.env)
    build_settings(args.build_env)
    if args.action == "static":
        manifests(settings, "https://sso.example.test", "", {component: f"iam-{component}:static" for component in COMPONENTS})
        return
    images = image_refs(args.build_env, args.registry_env)
    url, ca = keycloak_tls(args.keycloak_env)
    items = manifests(settings, url, ca, images)
    if args.action == "render":
        print(manifest_text(items))
        return
    if not args.context.strip():
        raise ValueError("KUBE_CONTEXT를 명시하세요.")
    deploy(args.context, args.env, args.keycloak_env, settings, items, images, check_only=args.action == "check")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, SetupError, KeyError) as error:
        print(f"IAM 배포 실패: {error}", file=sys.stderr)
        sys.exit(1)
