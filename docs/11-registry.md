# Registry

A registry is any Git repository with a `registry.yaml` manifest at its root. Anyone can host one — there is no central server. Definitions are fetched as plain text and written to your local `.uio/` directory, after which they have no live dependency on the registry.

---

## Quick start

```bash
# Add a registry to uio.toml (see Configuration section below)
uio registry list                    # show configured registries
uio registry search summarise        # find definitions by name, description, or tag
uio registry install summarise       # copy the definition into .uio/
uio registry update                  # refresh cached manifests
```

---

## `registry.yaml` manifest schema

A registry repo must contain a `registry.yaml` at its root with this structure:

```yaml
version: 1
definitions:
  - name: summarise
    type: skill
    path: skills/summarise.skill.md
    description: Summarise text or a file
    tags: [text, productivity]

  - name: repo-health
    type: agent
    path: agents/repo-health.agent.md
    description: Multi-tool repo health check
    tags: [devops, git]

  - name: ask-docs
    type: prompt
    path: prompts/ask-docs.prompt.md
    description: Ask a focused question about a codebase
    tags: [docs]
```

| Field | Required | Description |
|---|---|---|
| `version` | Yes | Must be `1` |
| `definitions` | Yes | List of definition entries |
| `definitions[].name` | Yes | Identifier used in `uio registry search` and `uio registry install` |
| `definitions[].type` | Yes | `agent`, `skill`, or `prompt` |
| `definitions[].path` | Yes | Path to the definition file relative to the registry repo root |
| `definitions[].description` | Yes | One-line summary shown in search results |
| `definitions[].tags` | No | List of strings for tag-based search |

`uio validate` checks manifest schema when run against a registry repo directory.

---

## Configuring registries

Add `[[registries]]` entries to `uio.toml`:

```toml
[[registries]]
name            = "official"
url             = "https://github.com/uio-project/uio-registry"
ref             = "main"
enabled         = true
cache_ttl_hours = 24

[[registries]]
name    = "my-team"
url     = "https://github.com/acme/uio-agents"
ref     = "v1.2.0"
enabled = true
```

| Key | Default | Description |
|---|---|---|
| `name` | required | Identifier shown in `registry list` and `--registry` filter |
| `url` | required | Git repo HTTPS URL |
| `ref` | `main` | Branch name, tag, or commit SHA |
| `enabled` | `true` | Skip this registry when `false` |
| `cache_ttl_hours` | — | How many hours the cached manifest is considered fresh. Omit to serve the cache indefinitely (until `uio registry update` is run) |

---

## `uio registry list`

Shows all configured registries:

```
$ uio registry list

  NAME      URL                                         REF   ENABLED
  ────────────────────────────────────────────────────────────────────
  official  https://github.com/uio-project/uio-registry       main  yes
  my-team   https://github.com/acme/uio-agents           v1.2  yes
```

---

## `uio registry search`

Searches for definitions by name, description, or tags (case-insensitive). Disabled registries are skipped. Network errors on one registry do not stop searching others.

```bash
uio registry search summarise
uio registry search "text productivity"
uio registry search devops --registry official
```

Example output:

```
$ uio registry search code

  NAME          TYPE   REGISTRY  DESCRIPTION
  ─────────────────────────────────────────────────────────────────────
  explain-code  skill  official  Explain a source file in plain English
  code-review   agent  official  Multi-turn code review with inline comments
```

---

## `uio registry install`

Fetches a definition from the first registry that contains it and writes it to the appropriate `.uio/` subdirectory.

```bash
uio registry install summarise
uio registry install repo-health --registry official
uio registry install summarise --force        # overwrite existing
uio registry install repo-health --pin        # lock to current SHA
```

After installation:
- The definition is a plain local file — editable, no live registry dependency
- `uio validate` runs automatically and prints any warnings

### `--force`

By default, `install` refuses to overwrite an existing definition. Use `--force` to overwrite:

```bash
uio registry install summarise --force
```

### `--pin`

`--pin` resolves the registry's branch ref to the current HEAD commit SHA and prints the `uio.toml` stanza to paste:

```
$ uio registry install repo-health --pin

  Installed: .uio/agents/repo-health.agent.md  (from registry 'official')

  Pin SHA: abc123def456789abcdef012
  To pin, update uio.toml:
    [[registries]]
    name = "official"
    url  = "https://github.com/uio-project/uio-registry"
    ref  = "abc123def456"
```

Pinning to a commit SHA ensures the installed definition and future fetches match exactly. Pinning is only supported for GitHub-hosted registries; for other hosts `--pin` prints a warning and continues.

A mutable `ref` (branch name) is not blocked, but it means the definition may silently change between installs. For production use, pin to a tag or SHA.

---

## `uio registry update`

Force-refreshes all cached manifests, or a specific registry:

```bash
uio registry update
uio registry update --registry official
```

On success, prints the number of definitions per registry. Exits 1 if any registry fails to refresh.

---

## Manifest caching

Manifests are cached locally in `~/.cache/uio/registries/<name>.yaml`. The cache is used by default for all registry commands except `update`.

The `cache_ttl_hours` setting controls freshness:
- If no TTL is set, the cache is used indefinitely (until `uio registry update` is run manually)
- If a TTL is set and the cache file is older than `cache_ttl_hours`, the manifest is re-fetched
- If the network is unreachable and a (stale) cache exists, the stale cache is used as a fallback with a warning

---

## URL normalisation

uio constructs raw file URLs from the registry's HTTPS URL and `ref`:

| Host | Raw URL pattern |
|---|---|
| `github.com` | `https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}` |
| `gitlab.com` | `https://gitlab.com/{owner}/{repo}/-/raw/{ref}/{path}` |
| Other | `{url}/{ref}/{path}` (direct path append) |

GitHub authentication uses `GITHUB_PERSONAL_ACCESS_TOKEN` or `GITHUB_TOKEN` for both manifest fetches and definition file fetches, enabling private registry repositories.

---

## Hosting a registry

To host your own registry:

1. Create a Git repository (public or private).
2. Create `registry.yaml` at the repository root following the schema above.
3. Add your definition files in subdirectories matching the `path` fields in `registry.yaml`.
4. Push to a branch or create a tag.
5. Add the registry to `uio.toml` in your projects.

Example repo layout:

```
uio-my-registry/
├── registry.yaml
├── agents/
│   └── deploy-checker.agent.md
├── skills/
│   └── extract-todos.skill.md
└── prompts/
    └── standup-summary.prompt.md
```

The repository at `https://github.com/uio-project/uio-registry` is the official registry and can be used as a reference.

---

## Security model

- **Definitions are plain text files.** Installing a definition does not execute code; it writes a markdown file to `.uio/`. The user decides whether to run it.
- The trust model is identical to `pip install`: you are trusting the definition author. Read installed definitions before running them.
- `uio validate` runs after every `install` and warns on unknown frontmatter keys, which can catch injected or malformed metadata.
- Pinning to a commit SHA is the safest option for production use — mutable branch refs can change after install.
- For private registries, the `GITHUB_TOKEN` must have `contents: read` on the registry repository.
