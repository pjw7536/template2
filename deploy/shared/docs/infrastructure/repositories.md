# 사내 저장소·이미지·패키지 미러

[사내 인프라 정보](README.md) · [공통 배포 문서](../README.md)

사내 Git·registry·패키지·artifact 주소와 전체 public/mirror 이름 매핑의 관리 원본입니다.

기록 형식과 갱신 절차는 [공통 기록 규칙](README.md#기록-규칙)을 따릅니다.
담당자는 미확인입니다. 설정 원본과 실제 사용·접속 여부는 아래 항목을 따릅니다.

## 사내 저장소 주소

### 공통 주소와 경로 규칙

| 용도 | 주소·패턴 | 근거·확인 상태 |
| --- | --- | --- |
| 사내 Git 서버·프로젝트 clone URL | 미확인 | 사내 Git 주소·프로젝트 경로·배포 브랜치 제공 필요 |
| 이미지 registry | `repository.samsungds.net/<mirror>/<image>:<tag>` | Airflow build·MinIO·Monitoring·Headlamp env와 Keycloak Kustomize의 선언 |
| Nexus 패키지·Raw 저장소 | `http://repository.samsungds.net/repository/<mirror>` | Airflow build env·Worker 설치 절차의 주소 패턴. 실제 하위 경로·CA·인증·권한 확인 필요 |
| PyPI simple index | `http://repository.samsungds.net/repository/<mirror>/simple` | Airflow build env의 선언 |
| 전체 public URL ↔ mirror 이름 | [패키지 미러 매핑](#전체-publicmirror-이름-매핑) | 생태계별 이름 목록. 실제 사용 주소는 아래 표에서 관리 |

### 이미지·패키지별 사용 주소

| 용도 | 주소 | 근거 |
| --- | --- | --- |
| Docker Hub 이미지 | `repository.samsungds.net/proxy-docker-registry-1.docker.io/<image>:<tag>` | Airflow build env·MinIO env·Monitoring env |
| FTP 이미지 | `repository.samsungds.net/proxy-docker-registry-1.docker.io/fauria/vsftpd@sha256:6d71d7c7f1b0ab2844ec7dc7999a30aef6d758b6d8179cf5967513f87c79c177` | `deploy/ftp/env/prod.env`의 `FTP_IMAGE` 선언. 미러의 digest 제공·실제 pull·CA·인증·담당자 미확인 |
| Quay 이미지 | `repository.samsungds.net/proxy-docker-quay.io/<image>:<tag>` | Keycloak Kustomize·Monitoring env |
| GHCR 이미지 | `repository.samsungds.net/proxy-docker-ghcr.io/<image>:<tag>` | Monitoring·Headlamp env |
| Kubernetes 이미지 | `repository.samsungds.net/proxy-docker-registry.k8s.io/<image>:<tag>` | Worker 설치 절차의 입력 |
| Debian APT | `http://repository.samsungds.net/repository/proxy-apt-mirror.kakao.com-debian` | Airflow `APT_DEBIAN_REPOSITORY` |
| Ubuntu APT | `http://repository.samsungds.net/repository/proxy-apt-archive.ubuntu.com-ubuntu` | Worker 설치 절차의 입력 |
| Docker APT | `http://repository.samsungds.net/repository/proxy-apt-download.docker.com-linux-ubuntu` | Worker 설치 절차의 입력 |
| Kubernetes v1.36 APT | `http://repository.samsungds.net/repository/proxy-apt-pkgs.k8s.io-core-stable/v1.36/deb/` | Worker 설치 절차의 주소 조합. 실제 패키지 제공 여부 미확인 |
| Kubernetes 공개 서명키 | `http://repository.samsungds.net/repository/proxy-raw-pkgs.k8s.io-core-stable/v1.36/deb/Release.key` | Worker 설치 절차의 주소 조합. 실제 하위 경로 미확인 |
| Headlamp Helm chart 0.45.0 | `http://repository.samsungds.net/repository/proxy-raw-github.com/kubernetes-sigs/headlamp/releases/download/headlamp-helm-0.45.0/headlamp-0.45.0.tgz` | `deploy/headlamp/helm/chart.lock.json`의 고정 다운로드 주소 |
| Airflow Helm chart 1.22.0 | `http://repository.samsungds.net/repository/proxy-helm-airflow.apache.org` | `deploy/airflow/helm/chart.lock.json`의 `repository` 선언. `fetch-chart`가 Helm index에서 고정 버전 패키지를 선택. 실제 패키지 제공·다운로드 가능 여부는 CP1에서 확인 필요 |
| Monitoring Helm chart 91.4.0 | `http://repository.samsungds.net/repository/proxy-raw-github.com/prometheus-community/helm-charts/releases/download/kube-prometheus-stack-91.4.0/kube-prometheus-stack-91.4.0.tgz` | `deploy/monitoring/helm/chart.lock.json`의 고정 다운로드 주소. 실제 패키지 제공·다운로드 가능 여부는 CP1에서 확인 필요 |
| 기본 PyPI | `http://repository.samsungds.net/repository/proxy-pypi-files.pythonhosted.org/simple` | Airflow `PIP_INDEX_URL` |
| 추가 사내 PyPI | `http://nexus.adpaas.cloud.samsungds.net/repository/dataservice-pypi/simple` | Airflow `PIP_EXTRA_INDEX_URL`. proxy 미러 매핑과 별도로 관리하는 저장소 |
| Impala ODBC 2.8.3.1008 | `http://nexus.adpaas.cloud.samsungds.net/repository/dataservice/odbc/linux/debian/clouderaimpalaodbc_2.8.3.1008-2_amd64.deb` | Airflow `BIGDATAQUERY_ODBC_DEB_URL`의 서버 전용 artifact |

위 주소의 실제 운영 사용·접속 성공·CA·인증·권한은 미확인입니다. URL의 scheme은 원본 입력을 따릅니다.
근거 파일은 `deploy/airflow/env/build.env`, `deploy/airflow/helm/chart.lock.json`, `deploy/minio/env/prod.env`, `deploy/keycloak/k8s/kustomization.yaml`,
`deploy/monitoring/env/k8s.env`, `deploy/monitoring/helm/chart.lock.json`, `deploy/headlamp/env/k8s.env`와 [Worker 설치 절차](../kubernetes/worker.md#2-0-사용할-사내-미러와-준비-파일)입니다.
선택 checkout에 없는 앱은 해당 앱을 선택한 뒤 입력을 확인합니다.

## 전체 public/mirror 이름 매핑

아래는 사용자가 제공한 사내 미러 이름 매핑입니다. 실제 사용 주소와 접속 여부는 위 표를 따릅니다.
`type`은 아래 절로 구분한 패키지 생태계, `public`은 외부 원본 URL, `mirror`는 사내 저장소 이름입니다. 같은 생태계·원본 URL·이름 조합은 한 번씩 유지합니다.
이름이 다르면 별도 항목이며 이름만으로 실제 URL·하위 경로·지원 버전·접속 성공을 확정하지 않습니다.
실제 최종 사용 주소는 위 표에 기록하고, 전체 매핑은 아래에서 관리합니다.

바로 찾기: [Docker](#docker) · [Helm](#helm) · [npm](#npm) · [PyPI](#pypi) · [apt](#apt) · [yum](#yum).

### apt

| public | mirror |
| --- | --- |
| `https://download.docker.com/linux/ubuntu` | `proxy-apt-download.docker.com-linux-ubuntu` |
| `https://packages.cloud.google.com/apt/` | `proxy-apt-packages.cloud.google.com-apt` |
| `https://apt.kitware.com` | `proxy-apt-apt.kitware.com` |
| `https://artifacts.elastic.co` | `proxy-apt-artifacts.elastic.co` |
| `https://broadcom.jfrog.io/artifactory/vcfcli-debian/` | `proxy-apt-broadcom.jfrog.io-artifactory-vcfcli-debian` |
| `https://cli.github.com/` | `proxy-apt-cli.github.com` |
| `http://deb.debian.org/` | `proxy-apt-deb.debian.org` |
| `https://archive.ubuntu.com/ubuntu` | `proxy-apt-archive.ubuntu.com-ubuntu` |
| `http://download.ceph.com/` | `proxy-apt-download.ceph.com` |
| `http://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu/` | `proxy-apt-ppa.launchpadcontent.net-deadsnakes-ppa-ubuntu` |
| `https://download.docker.com/linux/debian` | `proxy-apt-download.docker.com-linux-debian` |
| `https://pkgs.k8s.io/core:/stable:` | `proxy-apt-pkgs.k8s.io-core-stable` |
| `http://ppa.launchpadcontent.net/maas/3.5/ubuntu` | `proxy-apt-ppa.launchpadcontent.net-maas-3.5-ubuntu` |
| `http://ppa.launchpadcontent.net/maas/3.6/ubuntu` | `proxy-apt-ppa.launchpadcontent.net-maas-3.6-ubuntu` |
| `https://linux.mellanox.com/public/repo/` | `proxy-apt-linux.mellanox.com-public-repo` |
| `http://mirror.kakao.com/debian/` | `proxy-apt-mirror.kakao.com-debian` |
| `https://provo-mirror.opensuse.org/` | `proxy-apt-provo-mirror.opensuse.org` |
| `https://packagecloud.io/allegro/ralph` | `proxy-apt-packagecloud.io-allegro-ralph` |
| `http://mirror.kakao.com/ubuntu/` | `proxy-apt-mirror.kakao.com-ubuntu` |
| `https://snapcraft.io/store` | `proxy-apt-snapcraft.io-store` |
| `http://ftp.kaist.ac.kr/debian/` | `proxy-apt-ftp.kaist.ac.kr-debian` |
| `http://ftp.kaist.ac.kr/ubuntu/` | `proxy-apt-ftp.kaist.ac.kr-ubuntu` |
| `https://images.maas.io/ephemeral-v3/stable` | `proxy-apt-images.maas.io-ephemeral-v3-stable` |
| `http://developer.download.nvidia.com/compute/cuda/repos/` | `proxy-apt-developer.download.nvidia.com-compute-cuda-repos` |
| `https://nvidia.github.io/nvidia-container-runtime` | `proxy-apt-nvidia.github.io-nvidia-container-runtime` |
| `http://pkg.jenkins.io/debian` | `proxy-apt-pkg.jenkins.io-debian` |
| `https://download.postgresql.org/pub/repos/apt/` | `proxy-apt-download.postgresql.org-pub-repos-apt` |
| `http://archive.raspbian.org/raspbian/` | `proxy-apt-archive.raspbian.org-raspbian` |
| `http://packages.ros.org` | `proxy-apt-packages.ros.org` |
| `https://repo.scala-sbt.org` | `proxy-apt-repo.scala-sbt.org` |
| `http://ports.ubuntu.com/` | `proxy-apt-ports.ubuntu.com` |
| `https://repo.zabbix.com/zabbix/6.0/ubuntu` | `proxy-apt-repo.zabbix.com-zabbix-6.0-ubuntu` |

### cargo

| public | mirror |
| --- | --- |
| `https://index.crates.io/` | `proxy-cargo-index.crates.io` |

### conan

| public | mirror |
| --- | --- |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local` | `proxy-conan-v1-milvus01.jfrog.io-default-conan-local` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local` | `proxy-conan-v2-milvus01.jfrog.io-default-conan-local` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2` | `proxy-conan-v1-milvus01.jfrog.io-default-conan-local2` |
| `https://milvus01.jfrog.io/artifactory/api/conan/default-conan-local2` | `proxy-conan-v2-milvus01.jfrog.io-default-conan-local2` |

### conda

| public | mirror |
| --- | --- |
| `https://conda.anaconda.org/` | `proxy-conda-conda.anaconda.org` |
| `https://conda.anaconda.org/conda-forge` | `proxy-conda-conda.anaconda.org-conda-forge` |
| `https://conda.anaconda.org/nvidia` | `proxy-conda-conda.anaconda.org-nvidia` |
| `https://conda.anaconda.org/pytorch/` | `proxy-conda-conda.anaconda.org-pytorch` |
| `https://conda.anaconda.org/rapidsai` | `proxy-conda-conda.anaconda.org-rapidsai` |
| `https://conda.anaconda.org/ucb-bar` | `proxy-conda-conda.anaconda.org-ucb-bar` |
| `https://repo.continuum.io/pkgs/free/` | `proxy-conda-repo.continuum.io-pkgs-free` |

### docker

| public | mirror |
| --- | --- |
| `https://public.ecr.aws/` | `proxy-docker-public.ecr.aws` |
| `https://docker.bintray.io` | `proxy-docker-docker.bintray.io` |
| `https://projects.packages.broadcom.com` | `proxy-docker-projects.packages.broadcom.com` |
| `https://broadcom-vcf-cli-docker.jfrog.io` | `proxy-docker-broadcom-vcf-cli-docker.jfrog.io` |
| `https://broadcom-vcfa.jfrog.io` | `proxy-docker-broadcom-vcfa.jfrog.io` |
| `https://broadcom-vsphere-docker.jfrog.io` | `proxy-docker-broadcom-vsphere-docker.jfrog.io` |
| `https://container-registry.oracle.com` | `proxy-docker-container-registry.oracle.com` |
| `https://docker.elastic.co/` | `proxy-docker-docker.elastic.co` |
| `https://registry-1.docker.io/` | `proxy-docker-registry-1.docker.io` |
| `https://downloads.unstructured.io` | `proxy-docker-downloads.unstructured.io` |
| `https://gcr.io` | `proxy-docker-gcr.io` |
| `https://ghcr.io/` | `proxy-docker-ghcr.io` |
| `https://releases-docker.jfrog.io` | `proxy-docker-releases-docker.jfrog.io` |
| `https://registry.k8s.io/` | `proxy-docker-registry.k8s.io` |
| `https://k8s.gcr.io` | `proxy-docker-k8s.gcr.io` |
| `https://mcr.microsoft.com` | `proxy-docker-mcr.microsoft.com` |
| `https://nvcr.io/` | `proxy-docker-nvcr.io` |
| `https://registry-1.docker.io/` | `proxy-docker-registry-1.docker.io-proteantecs` |
| `https://public.ecr.aws` | `proxy-docker-public.ecr.aws` |
| `https://quay.io/` | `proxy-docker-quay.io` |

### go

| public | mirror |
| --- | --- |
| `https://proxy.golang.org` | `proxy-go-proxy.golang.org` |

### helm

| public | mirror |
| --- | --- |
| `https://airflow.apache.org/` | `proxy-helm-airflow.apache.org` |
| `https://charts.bitnami.com/bitnami` | `proxy-helm-charts.bitnami.com-bitnami` |

### maven2

| public | mirror |
| --- | --- |
| `https://packages.atlassian.com/mvn/maven-external/` | `proxy-maven2-packages.atlassian.com-mvn-maven-external` |
| `https://css4j.github.io/maven/` | `proxy-maven2-css4j.github.io-maven` |
| `https://plugins.gradle.org/` | `proxy-maven2-plugins.gradle.org` |
| `https://jcenter.bintray.com` | `proxy-maven2-jcenter.bintray.com` |
| `https://maven.google.com` | `proxy-maven2-maven.google.com` |
| `https://maven.anypoint.mulesoft.com/api/v3/maven` | `proxy-maven2-maven.anypoint.mulesoft.com-api-v3-maven` |
| `https://nexus.xwiki.org/nexus/` | `proxy-maven2-nexus.xwiki.org-nexus` |
| `https://repo1.maven.org/maven2/` | `proxy-maven2-repo1.maven.org-maven2` |
| `https://repo.spring.io/plugins-release/` | `proxy-maven2-repo.spring.io-plugins-release` |
| `https://maven.xwiki.org/releases/` | `proxy-maven2-maven.xwiki.org-releases` |

### npm

| public | mirror |
| --- | --- |
| `https://nexus.dev.morpheus.kr/repository/npm/` | `proxy-npm-nexus.dev.morpheus.kr-repository-npm` |
| `https://packages.morpheus.kr/repository/npm-release/` | `proxy-npm-packages.morpheus.kr-repository-npm-release` |
| `https://registry.npmjs.org` | `proxy-npm-registry.npmjs.org` |
| `https://registry.yarnpkg.com` | `proxy-npm-registry.yarnpkg.com` |

### nuget

| public | mirror |
| --- | --- |
| `https://www.nuget.org/` | `proxy-nuget-www.nuget.org` |

### pypi

| public | mirror |
| --- | --- |
| `https://pypi.nvidia.com/` | `proxy-pypi-pypi.nvidia.com` |
| `https://files.pythonhosted.org` | `proxy-pypi-files.pythonhosted.org` |
| `https://download.pytorch.org/whl/` | `proxy-pypi-download.pytorch.org-whl` |

### r

| public | mirror |
| --- | --- |
| `https://cran.r-project.org/` | `proxy-r-cran.r-project.org` |

### raw

| public | mirror |
| --- | --- |
| `https://dl-cdn.alpinelinux.org/alpine` | `proxy-raw-dl-cdn.alpinelinux.org-alpine` |
| `https://broadcom.jfrog.io/artifactory/photon/` | `proxy-raw-broadcom.jfrog.io-artifactory-photon` |
| `https://broadcom.jfrog.io/artifactory/vcf-distro` | `proxy-raw-broadcom.jfrog.io-artifactory-vcf-distro` |
| `https://dl.k8s.io` | `proxy-raw-dl.k8s.io` |
| `https://developer.download.nvidia.com/compute/cuda/` | `proxy-raw-developer.download.nvidia.com-compute-cuda` |
| `https://dl.google.com/android/repository` | `proxy-raw-dl.google.com-android-repository` |
| `https://developer.download.nvidia.com/compute/redist/gdrcopy` | `proxy-raw-developer.download.nvidia.com-compute-redist-gdrcopy` |
| `https://github.com/electron/electron/releases/download` | `proxy-raw-github.com-electron-electron-releases-download` |
| `https://github.com/indygreg` | `proxy-raw-github.com-indygreg` |
| `https://github.com/` | `proxy-raw-github.com` |
| `https://download.ni.com` | `proxy-raw-download.ni.com` |
| `https://data.pyg.org` | `proxy-raw-data.pyg.org` |
| `https://downloads.python.org` | `proxy-raw-downloads.python.org` |
| `https://provo-mirror.opensuse.org/` | `proxy-raw-provo-mirror.opensuse.org` |
| `https://dl.google.com/dl/android/maven2/` | `proxy-raw-dl.google.com-dl-android-maven2` |
| `https://pkgs.k8s.io/` | `proxy-raw-pkgs.k8s.io` |
| `https://nvidia.github.io/libnvidia-container` | `proxy-raw-nvidia.github.io-libnvidia-container` |
| `https://repository.mulesoft.org/releases/` | `proxy-raw-repository.mulesoft.org-releases` |
| `https://nvidia.github.io/nvidia-container-runtime/` | `proxy-raw-nvidia.github.io-nvidia-container-runtime` |
| `https://developer.download.nvidia.com/compute/cuda/repos/` | `proxy-raw-developer.download.nvidia.com-compute-cuda-repos` |
| `https://open-vsx.org/` | `proxy-raw-open-vsx.org` |
| `https://packages.microsoft.com/` | `proxy-raw-packages.microsoft.com` |
| `https://pkgs.k8s.io/core:/stable:` | `proxy-raw-pkgs.k8s.io-core-stable` |
| `https://storage.googleapis.com` | `proxy-raw-storage.googleapis.com` |
| `http://download.tizen.org/` | `proxy-raw-download.tizen.org` |
| `https://ftp.kaist.ac.kr/ubuntu-cd/` | `proxy-raw-ftp.kaist.ac.kr-ubuntu-cd` |
| `https://github.com/astral-sh/python-build-standalone/releases/download` | `proxy-raw-github.com-astral-sh-python-build-standalone-releases-download` |
| `https://wp-content.vmware.com/` | `proxy-raw-wp-content.vmware.com` |

### rubygems

| public | mirror |
| --- | --- |
| `https://rubygems.org/` | `proxy-rubygems-rubygems.org` |

### yum

| public | mirror |
| --- | --- |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/ansible/2.9/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-ansible-2.9-os` |
| `https://repos.azul.com/zulu/rpm` | `proxy-yum-repos.azul.com-zulu-rpm` |
| `https://broadcom.jfrog.io/artifactory/vcfcli-rpm/` | `proxy-yum-broadcom.jfrog.io-artifactory-vcfcli-rpm` |
| `http://mirror.stream.centos.org/9-stream/` | `proxy-yum-mirror.stream.centos.org-9-stream` |
| `https://vault.centos.org/` | `proxy-yum-vault.centos.org` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-codeready-builder-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/aarch64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-aarch64-codeready-builder-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/codeready-builder/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-codeready-builder-os` |
| `https://packages.confluent.io/` | `proxy-yum-packages.confluent.io` |
| `https://packages.daos.io/` | `proxy-yum-packages.daos.io` |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/fast-datapath/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-fast-datapath-os` |
| `https://dl.fedoraproject.org/pub/archive/epel/` | `proxy-yum-dl.fedoraproject.org-pub-archive-epel` |
| `https://dl.fedoraproject.org/pub/fedora` | `proxy-yum-dl.fedoraproject.org-pub-fedora` |
| `https://dl.fedoraproject.org/pub/epel/` | `proxy-yum-dl.fedoraproject.org-pub-epel` |
| `https://dl.fedoraproject.org/pub/archive/fedora/` | `proxy-yum-dl.fedoraproject.org-pub-archive-fedora` |
| `https://releases.jfrog.io/artifactory/jfrog-rpms` | `proxy-yum-releases.jfrog.io-artifactory-jfrog-rpms` |
| `http://ftp.kaist.ac.kr/opensuse/` | `proxy-yum-ftp.kaist.ac.kr-opensuse` |
| `https://al2023-repos-ap-northeast-2-de612dc2.s3.dualstack.ap-northeast-2.amazonaws.com` | `proxy-yum-al2023-repos-ap-northeast-2-de612dc2.s3.dualstack.ap-northeast-2.amazonaws.com` |
| `https://yum.oracle.com/repo/OracleLinux/` | `proxy-yum-yum.oracle.com-repo-oraclelinux` |
| `https://mirror.stream.centos.org/10-stream/` | `proxy-yum-mirror.stream.centos.org-10-stream` |
| `https://nvidia.github.io/nvidia-docker` | `proxy-yum-nvidia.github.io-nvidia-docker` |
| `https://nvidia.github.io/libnvidia-container/` | `proxy-yum-nvidia.github.io-libnvidia-container` |
| `https://artifacts.opensearch.org/` | `proxy-yum-artifacts.opensearch.org` |
| `https://cdn.redhat.com/content/dist/layered/rhel8/x86_64/openstack/16.2/os` | `proxy-yum-cdn.redhat.com-content-dist-layered-rhel8-x86_64-openstack-16.2-os` |
| `https://www.pgpool.net/yum/` | `proxy-yum-www.pgpool.net-yum` |
| `http://pkg.jenkins.io/redhat-stable` | `proxy-yum-pkg.jenkins.io-redhat-stable` |
| `https://download.postgresql.org/pub/repos/yum/` | `proxy-yum-download.postgresql.org-pub-repos-yum` |
| `https://repo.radeon.com` | `proxy-yum-repo.radeon.com` |
| `https://cdn.redhat.com/content/dist/rhel/server/7/7Server/x86_64/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel-server-7-7Server-x86_64-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/highavailability/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-highavailability-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.4/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.4-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.6/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.6-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.6/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.6-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.8/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.8-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel8/8.8/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel8-8.8-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8.10/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8.10-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel8/8.10/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel8-8.10-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.2/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.2-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.2/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.2-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.4/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.4-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.4/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.4-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel9/9.6/aarch64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9.6-aarch64-appstream-os` |
| `https://cdn.redhat.com/content/dists/rhel9/9.6/aarch64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel9-9.6-aarch64-baseos-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.6/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.6-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/eus/rhel9/9.6/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-eus-rhel9-9.6-x86_64-baseos-os` |
| `https://cdn.redhat.com/content/dist/rhel10/10.0/x86_64/appstream/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel10-10.0-x86_64-appstream-os` |
| `https://cdn.redhat.com/content/dist/rhel10/10.0/x86_64/baseos/os` | `proxy-yum-cdn.redhat.com-content-dist-rhel10-10.0-x86_64-baseos-os` |
| `https://dl.rockylinux.org/vault/rocky/` | `proxy-yum-dl.rockylinux.org-vault-rocky` |
| `http://download.ceph.com/` | `proxy-yum-download.ceph.com` |
| `https://cli.github.com/` | `proxy-yum-cli.github.com` |
| `http://mirror.kakao.com/epel/` | `proxy-yum-mirror.kakao.com-epel` |
| `http://mirror.kakao.com/centos/` | `proxy-yum-mirror.kakao.com-centos` |
| `http://mirror.kakao.com/opensuse/` | `proxy-yum-mirror.kakao.com-opensuse` |
| `https://mirror.navercorp.com/rocky/` | `proxy-yum-mirror.navercorp.com-rocky` |
| `https://download.docker.com/linux/centos` | `proxy-yum-download.docker.com-linux-centos` |
| `https://packages.cloud.google.com/yum/` | `proxy-yum-packages.cloud.google.com-yum` |
| `https://pkgs.k8s.io/` | `proxy-yum-pkgs.k8s.io` |
| `https://linux.mellanox.com/public/repo/` | `proxy-yum-linux.mellanox.com-public-repo` |
| `https://provo-mirror.opensuse.org/` | `proxy-yum-provo-mirror.opensuse.org` |
| `https://download.docker.com/linux/rhel` | `proxy-yum-download.docker.com-linux-rhel` |
| `https://repo.zabbix.com/` | `proxy-yum-repo.zabbix.com` |
| `https://repo.zabbix.com/zabbix/5.0/rhel/7/` | `proxy-yum-repo.zabbix.com-zabbix-5.0-rhel-7` |

## 추가 확인·변경 연계

- 사내 Git 서버·프로젝트 clone URL·배포 브랜치는 미확인입니다.
- npm의 사내 최종 URL과 Helm chart의 실제 패키지 제공 여부·CA·권한 신청 절차는 추가 확인이 필요합니다.
- 사내 서버는 승인된 미러 또는 반입 파일, 외부 PC 개발은 public source를 사용합니다.
- 주소·버전을 바꾸면 소비 앱의 env·Kustomize·chart lock과 설치 문서도 대조합니다. 인증값은 기록하지 않습니다.
