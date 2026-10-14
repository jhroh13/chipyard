FROM mcr.microsoft.com/devcontainers/base:1-ubuntu24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER root
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bc build-essential bzip2 ca-certificates curl findutils git gzip kmod \
    make openssh-client patch procps python3 tar unzip util-linux wget xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Match the Miniforge bootstrap used by Chipyard's upstream Dockerfile.
RUN curl -fsSL --retry 3 \
      https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
      -o /tmp/Miniforge3-Linux-x86_64.sh \
    && curl -fsSL --retry 3 \
      https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh.sha256 \
      -o /tmp/Miniforge3-Linux-x86_64.sh.sha256 \
    && cd /tmp && sha256sum -c Miniforge3-Linux-x86_64.sh.sha256 \
    && bash Miniforge3-Linux-x86_64.sh -b -p /opt/conda \
    && rm /tmp/Miniforge3-Linux-x86_64.sh /tmp/Miniforge3-Linux-x86_64.sh.sha256 \
    && chown -R vscode:vscode /opt/conda

ENV PATH="/opt/conda/bin:${PATH}"
USER vscode
