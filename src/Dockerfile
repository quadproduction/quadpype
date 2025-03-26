# Build QuadPype docker image
FROM debian:bookworm AS builder
USER root

ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_DATE
ARG VERSION

LABEL maintainer="dev@quad.fr"
LABEL description="Docker Image to build and run QuadPype under Ubuntu 22.04"
LABEL org.opencontainers.image.name="quad/quadpype"
LABEL org.opencontainers.image.title="QuadPype Docker Image"
LABEL org.opencontainers.image.url="https://github.com/quadproduction/quadpype"
LABEL org.opencontainers.image.source="https://github.com/quadproduction/quadpype"
LABEL org.opencontainers.image.documentation="https://github.com/quadproduction/quadpype/wiki"
LABEL org.opencontainers.image.created=$BUILD_DATE
LABEL org.opencontainers.image.version=$VERSION

# Update base
RUN apt-get update -y

RUN apt-get install -y --no-install-recommends ca-certificates

RUN echo "deb [trusted=yes] https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu/ jammy main" >> /etc/apt/sources.list

RUN apt-get update --allow-insecure-repositories -y \
    && apt-get install -y --no-install-recommends \
    bash git cmake make curl wget build-essential libcrypt-dev libssl-dev zlib1g-dev libbz2-dev iputils-ping \
    libreadline-dev libsqlite3-dev llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev \
    liblzma-dev patchelf libgl1 libxcb-* libxkbcommon* libdbus-1-3 libgtk2.0-dev libegl1-mesa libxau-dev \
    libpng16-16 libbrotli-dev libfreetype6-dev python3.9 python3.9-dev 3.9-distutils python3.9-venv

RUN ln -sf /usr/bin/python3.9 /usr/bin/python3
RUN ln -sf /usr/bin/python3.9 /usr/bin/python

# Clone QuadPype
RUN cd /opt/ && \
    git clone --recurse-submodules https://github.com/quadproduction/quadpype.git && \
    cd quadpype && \
    git fetch --all --tags

WORKDIR /opt/quadpype

RUN git checkout enhancement/linux-dockerfile

SHELL ["/bin/bash", "--login", "-c"]

RUN source ~/.bashrc

# Ensure required scripts are executable
RUN chmod +x ./src/tools/activate.sh
RUN chmod +x ./src/tools/install_environment_no_pyenv.sh
RUN chmod +x ./src/tools/build.sh

# Create virtualenv
RUN ./src/tools/install_environment_no_pyenv.sh
RUN cd src/ && ./.poetry/bin/poetry lock

# Ensure venv is truly activate
RUN chmod +x ./src/.venv/bin/activate
RUN source ./src/.venv/bin/activate

# Build quadpype
RUN ./src/tools/build.sh
