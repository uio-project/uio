FROM python:3.11-slim

# Node.js 20 LTS — required for GitHub MCP server and other @modelcontextprotocol packages
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

WORKDIR /workspace

# Install uio from source
COPY . /build
RUN pip install --no-cache-dir /build && rm -rf /build

# Pre-warm the npx cache for bundled MCP servers so the first agent run is fast
RUN for pkg in \
        @github/github-mcp-server \
        @modelcontextprotocol/server-filesystem \
        @modelcontextprotocol/server-fetch \
        @modelcontextprotocol/server-memory; \
    do npx -y "$pkg" --version 2>/dev/null || true; done

# /workspace is the default mount point for uio.toml and .uio/ definitions.
# uio.toml must exist in the current working directory — mount your project here.
VOLUME ["/workspace"]

# API keys — always pass at runtime, never bake into the image
ENV GEMINI_API_KEY="" \
    OPENAI_API_KEY="" \
    GITHUB_PERSONAL_ACCESS_TOKEN=""

ENTRYPOINT ["uio"]
CMD ["--help"]
