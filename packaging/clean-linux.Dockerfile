# Disposable acceptance image. No Python, Node, npm or Git is installed.
ARG BASE=ubuntu:22.04
FROM ${BASE}
RUN . /etc/os-release && audio=libasound2 && if [ "$VERSION_ID" = "24.04" ]; then audio=libasound2t64; fi \
    && apt-get update && apt-get install -y --no-install-recommends xvfb xauth libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 "$audio" libxss1 libx11-xcb1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ! command -v python3 && ! command -v python && ! command -v node && ! command -v git
