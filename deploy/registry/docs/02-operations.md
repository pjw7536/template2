# 사내 이미지 저장소 운영

[앱 안내](../README.md) · 이전: [설치](01-install.md)

## 이미지 push 규칙

- 이미지 이름은 `store.etch.samsungds.net/<앱>:<고유 tag>`입니다. 같은 tag를 다시 push하지 않습니다.
- 이미지에 env·인증서·개인키·ODBC 설정 같은 비밀값을 넣지 않습니다. 노드는 익명으로 이미지를 내려받을 수 있습니다.
- 앱별 push 절차는 각 앱 문서를 따릅니다. Airflow는 [이미지 전달](../../airflow/docs/02-artifacts.md#registry를-사용하는-경우)입니다.

## 이미지 삭제와 용량 정리

Zot은 참조가 없는 blob을 24시간 주기로 정리합니다. 더 이상 쓰지 않는 tag는 운영 중인 앱의 tag가 아님을 확인한 뒤 삭제합니다.

```bash
kubectl --context kubernetes-admin@kubernetes get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' \
  | grep -F 'store.etch.samsungds.net/' | sort -u
```

삭제는 로그인한 계정으로 OCI API를 호출합니다. `skopeo`가 있는 host에서는 아래처럼 실행합니다.

```bash
skopeo delete --creds "$REGISTRY_USER" docker://store.etch.samsungds.net/test/busybox:1.37.0
```

저장 용량은 registry Worker에서 확인합니다.

```bash
sudo du -sh /appdata/registry
```

## push 계정 교체

새 htpasswd로 Secret을 교체한 뒤 Deployment를 재시작합니다. 기존 계정으로 로그인한 빌드 host는 다시 로그인합니다.

```bash
kubectl --context kubernetes-admin@kubernetes -n registry create secret generic registry-htpasswd \
  --from-file=htpasswd=/tmp/registry-htpasswd --dry-run=client -o yaml \
  | kubectl --context kubernetes-admin@kubernetes apply -f -
kubectl --context kubernetes-admin@kubernetes -n registry rollout restart deployment/registry
shred -u /tmp/registry-htpasswd
```

## 장애 영향

registry Pod가 중지되면 이미지를 아직 받지 않은 노드에서 새 Pod가 시작되지 않습니다. 이미 받은 이미지(`IfNotPresent`)로 실행 중인 Pod는 영향이 없습니다.
데이터는 Worker의 `DATA_HOST_PATH`에 있으며 PV는 `Retain`입니다. 다른 Worker로 옮기려면 서비스를 멈추고 폴더를 복사한 뒤 새 PV/PVC로 전환합니다.

## registry 주소로 전환

기존 Zot Service와 PV/PVC를 사용해 주소를 전환합니다.

1. DNS SAN에 `registry.etch.samsungds.net`을 포함한 인증서를 발급받아 공용 Traefik에 등록하고 새 DNS를 APP VIP로 연결합니다.
2. 전환 기간에는 두 호스트의 HTTPS 라우트를 같은 Zot Service로 연결합니다. 빌드 호스트에서 새 주소로 로그인하고, 기존 태그 pull과 테스트 이미지 push를 확인합니다.
3. 빌드 및 배포 설정의 이미지 참조를 새 주소로 옮깁니다. 이전 주소를 사용하는 배포·Job·롤백 설정까지 정리한 뒤 `store` 라우트를 내립니다.
