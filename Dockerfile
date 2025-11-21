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
RUN /home/agent/.local/bin/uv python install 3.13

ENV PATH="/home/agent/.local/bin:${PATH}"

COPY --chown=agent:agent dist/*.whl /tmp/
RUN uv tool install /tmp/*.whl && rm /tmp/*.whl

# Install local plugin wheels if any were built
COPY --chown=agent:agent dist-plugins* /tmp/plugin-wheels/
RUN if [ -d /tmp/plugin-wheels ] && [ "$(ls -A /tmp/plugin-wheels 2>/dev/null)" ]; then \
    echo "Installing local plugin wheels:" && \
    ls -lh /tmp/plugin-wheels/ && \
    for wheel in /tmp/plugin-wheels/*.whl /tmp/plugin-wheels/*.tar.gz; do \
        if [ -f "$wheel" ]; then \
            echo "  Installing: $(basename $wheel)" && \
            uvx --from mediagram mediagram plugin install "$wheel"; \
        fi \
    done && \
    rm -rf /tmp/plugin-wheels; \
    fi

# Install remote plugins if provided (PyPI packages or URLs)
ARG REMOTE_PLUGINS
RUN if [ -n "$REMOTE_PLUGINS" ]; then \
    echo "Installing remote plugins: $REMOTE_PLUGINS" && \
    for plugin in $REMOTE_PLUGINS; do \
        echo "  Installing: $plugin" && \
        uvx --from mediagram mediagram plugin install "$plugin"; \
    done; \
    fi

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace
CMD ["mediagram.telegram"]
