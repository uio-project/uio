FROM python:3.11-slim

# Node.js 20 LTS — required for @modelcontextprotocol/* MCP servers bundled in the
# default uio.toml. Investigation result (issue #155): no Python MCP server exposes
# the same tool names (read_file, list_directory, search_files, …) that agent
# definitions reference, so the official @modelcontextprotocol packages are kept.
# Removed from the original pre-warm list:
#   @modelcontextprotocol/server-git    → replaced by uvx mcp-server-git
#   @modelcontextprotocol/server-fetch  → not used in default uio.toml
#   @modelcontextprotocol/server-memory → not used in default uio.toml
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# gh CLI — fallback for agents that shell out to GitHub via run_command
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) \
        signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
        https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# github-mcp-server native Go binary — downloaded from GitHub Releases by the
# release workflow for both amd64 (Linux_x86_64) and arm64. Falls back
# gracefully for local builds where mcp-vendor/bin/ contains only .gitkeep.
COPY mcp-vendor/bin/ /tmp/mcp-bin/
RUN arch=$(uname -m | sed 's/aarch64/arm64/') && \
    if [ -f "/tmp/mcp-bin/github-mcp-server-${arch}" ]; then \
        cp "/tmp/mcp-bin/github-mcp-server-${arch}" /usr/local/bin/github-mcp-server && \
        chmod +x /usr/local/bin/github-mcp-server; \
    fi && \
    rm -rf /tmp/mcp-bin

# Pure-JS MCP packages are pre-bundled by the release workflow on the native
# runner (see the "Pre-bundle npm MCP packages" step in release.yml) and
# COPYed here so no npm network access is needed during the Docker build —
# this is especially valuable for the arm64 slice built under QEMU.
# mcp-vendor/node_modules/ is always present in the checkout (gitkeep placeholder),
# so this COPY succeeds even for local builds; the RUN fallback fires instead.
COPY mcp-vendor/node_modules/ /usr/local/lib/node_modules/
RUN if [ ! -d "/usr/local/lib/node_modules/@modelcontextprotocol/server-filesystem" ]; then \
        npm install -g \
            @modelcontextprotocol/server-filesystem \
            @modelcontextprotocol/server-sequential-thinking; \
    fi

WORKDIR /workspace

# Install uio from PyPI — version is injected at build time from pyproject.toml
ARG UIO_VERSION
RUN pip install --no-cache-dir "uio-ai==${UIO_VERSION}"

# /workspace is the default mount point for uio.toml and .uio/ definitions.
# uio.toml must exist in the current working directory — mount your project here.
VOLUME ["/workspace"]

# API keys — always pass at runtime, never bake into the image
ENV GEMINI_API_KEY="" \
    OPENAI_API_KEY="" \
    GITHUB_PERSONAL_ACCESS_TOKEN=""

ENTRYPOINT ["uio"]
CMD ["--help"]
