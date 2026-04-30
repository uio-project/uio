# Installation

## Prerequisites

- **Python 3.11 or later.** uio uses `tomllib` from the standard library (added in 3.11) and type annotation syntax that requires 3.11+. Check your version with `python3 --version`.
- **pip.** Comes with every standard Python installation.

You do not need Node.js to use uio's core features. Node.js is only needed if you want GitHub MCP server integration (see [MCP integration](08-mcp.md)).

---

## Install from PyPI

```bash
pip install uio
```

Verify the installation:

```bash
uio --version
# uio, version 0.1.0
```

---

## Optional: dev extras

The `dev` extras add the test runner and linter used during development:

```bash
pip install "uio[dev]"
```

This installs `pytest` and `ruff`. You only need this if you are running the test suite or contributing to uio itself.

---

## Install from source

For contributors or to run unreleased code:

```bash
git clone https://github.com/jomkz/uio.git
cd uio
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode — changes to the source tree take effect immediately without reinstalling.

Verify the test suite passes:

```bash
pytest
# 150+ tests, no API keys required
```

---

## Shell completion

uio can generate completion scripts for bash, zsh, and fish. Add the appropriate line to your shell's startup file.

**bash** — add to `~/.bashrc`:
```bash
eval "$(uio completion bash)"
```

**zsh** — add to `~/.zshrc`:
```bash
eval "$(uio completion zsh)"
```

**fish** — add to `~/.config/fish/config.fish`:
```fish
uio completion fish | source
```

Restart your shell or `source` the file to activate completion. You can then press Tab to complete `uio` subcommands, agent names, and flags.

---

## First-time setup

After installing, run `uio config show` to see what providers are available:

```
$ uio config show

  Provider chain (auto-routing order):
    gemini    GEMINI_API_KEY       ✗ not set
    openai    OPENAI_API_KEY       ✗ not set
    ollama    (no key required)    ✓ always available

  Default provider : (none — uses routing chain)
  Default model    : (none — inferred from provider)
  MCP github       : ✗ GITHUB_PERSONAL_ACCESS_TOKEN not set
  Cost ledger      : uio_cost.jsonl
  Timeout          : 300s
```

A `✗` next to a provider means its API key is not set — that provider is skipped in the auto-routing chain. Ollama is always available as a fallback (it needs no key, but the Ollama process must be running locally).

Set at least one API key before running agents:

```bash
export GEMINI_API_KEY=your-key-here
```

See [Providers](07-providers.md) for detailed setup instructions for each provider.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'google.genai'`**

The `google-genai` package is a dependency of uio and should install automatically. If it didn't:

```bash
pip install google-genai
```

**`ModuleNotFoundError: No module named 'openai'`**

```bash
pip install openai
```

**`uio chat` connects but Ollama returns a connection error**

The Ollama process must be running. Start it with `ollama serve`. The default endpoint is `http://localhost:11434/v1`. If your Ollama instance runs elsewhere, set `OLLAMA_BASE_URL`.

**`uio: command not found`**

The `uio` script is installed into your Python environment's `bin/` directory. If that directory is not on your `PATH`, either:
- Activate a virtual environment: `source .venv/bin/activate`
- Or add the directory to PATH: `export PATH="$HOME/.local/bin:$PATH"` (for user-level installs)

**Python version is 3.10 or older**

uio requires Python 3.11+. Install a newer version via your OS package manager, `pyenv`, or `deadsnakes` PPA (Ubuntu).
