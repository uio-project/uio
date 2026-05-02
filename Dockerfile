FROM python:3.11-slim

# Node.js 20 LTS — required solely for @modelcontextprotocol/server-filesystem.
# Investigation result (issue #155): no Python MCP server exposes the same tool
# names (read_file, list_directory, search_files, …) that agent definitions
# reference, so this dependency cannot be removed yet.
# All other previously-npx-based servers have been replaced:
#   @github/github-mcp-server              → native Go binary (github-mcp-server stdio)
#   @modelcontextprotocol/server-sequential-thinking → uvx sequential-thinking-mcp
#   @modelcontextprotocol/server-git        → uvx mcp-server-git
#   @modelcontextprotocol/server-fetch      → not used in default uio.toml (removed)
#   @modelcontextprotocol/server-memory     → not used in default uio.toml (removed)
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

# Install MCP server npm packages globally before ARG UIO_VERSION so this layer
# is cache-stable between releases (ARG changes bust all subsequent layers).
# Using npm install -g instead of npx pre-warm: packages land in
# /usr/local/lib/node_modules and their bins are on PATH, so runtime npx
# invocations resolve them without any network access.
RUN npm install -g \
        @github/github-mcp-server \
        @modelcontextprotocol/server-filesystem

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
