FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ffmpeg \
    wget \
    unzip \
    zip \
    tree \
    imagemagick \
    sed \
    gawk \
    gzip \
    bzip2 \
    xz-utils \
    p7zip-full \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash -u 1001 agent

RUN mkdir -p /workspace && chown agent:agent /workspace

USER agent

RUN curl -LsSf https://astral.sh/uv/install.sh | bash
RUN /home/agent/.local/bin/uv python install

ENV PATH="/home/agent/.local/bin:${PATH}"

COPY --chown=agent:agent dist/*.whl /tmp/
RUN uv tool install /tmp/*.whl && rm /tmp/*.whl

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace
CMD ["mediagram.telegram"]
