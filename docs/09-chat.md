# Chat REPL

`uio chat` starts an interactive, streaming, multi-turn conversation with an LLM. Unlike `agent run`, the chat REPL is not driven by a definition file — it uses a built-in general-purpose system prompt and accumulates conversation history for the duration of the session.

---

## Starting a session

```bash
uio chat
```

The header line shows the selected provider, model, and whether tools are enabled:

```
uio chat  [gemini/gemini-2.5-flash-lite]
Type /help for commands, Ctrl-D or /exit to quit.

You:
```

With tools enabled, the header shows `+tools`:

```
uio chat  [gemini/gemini-2.5-flash-lite +tools]
```

---

## Basic usage

Type any message and press Enter. The model's response streams to the terminal token-by-token. After the response, continue typing to add the next turn — the full conversation history is included on every request.

To end the session: type `/exit`, `/quit`, or press Ctrl-D.

---

## Slash commands

Inside the REPL, these commands are available:

| Command | Effect |
|---|---|
| `/help` | Show available slash commands |
| `/clear` | Clear the conversation history (the session continues with a fresh context) |
| `/cost` | Show token spend and estimated cost for this session so far |
| `/exit` | End the session |
| `/quit` | End the session (alias for `/exit`) |

---

## Provider and model

```bash
uio chat --provider ollama
uio chat --provider openai --model gpt-4o
uio chat --base-url http://localhost:4000   # LiteLLM proxy
```

The chat session always uses the `small` complexity tier (the default). If you need a specific model:

```bash
uio chat --model gemini-2.5-flash
```

---

## Tool use

By default, the model cannot run shell commands. Pass `--tools` to expose `run_command`:

```bash
uio chat --tools
```

When the model requests a shell command, the REPL prints the command and asks for approval:

```
  $ git log --oneline -5
  Execute? [Y/n]
```

Press Enter or `y` to approve. The command runs and its output is fed back to the model, which continues the response. Type `n` to reject — the model receives `[command rejected by user]` and can try a different approach.

---

## Auto-approve

Skip the approval prompt for all commands:

```bash
uio chat --auto-approve
```

`--auto-approve` implies `--tools`. Use this only when you are comfortable with the model running any shell command — it has no safety restrictions.

---

## Allow and deny glob patterns

For a middle ground between full approval prompts and `--auto-approve`, use `--allow` and `--deny` with shell glob patterns:

```bash
# Auto-approve git read commands; still prompt for everything else
uio chat --tools --allow 'git log*' --allow 'git diff*' --allow 'git status'

# Auto-approve everything EXCEPT git push
uio chat --auto-approve --deny 'git push*'

# Combine: approve git reads, deny destructive writes, prompt for the rest
uio chat --tools --allow 'git log*' --allow 'git diff*' --deny 'git push*' --deny 'rm -*'
```

Evaluation order:
1. **Deny patterns** are checked first. If the command matches any deny pattern, it is rejected without prompting.
2. **Allow patterns** are checked next. If the command matches any allow pattern, it is approved without prompting.
3. If no pattern matches and `--auto-approve` is not set, the user is prompted.

Both flags can be repeated: `--allow 'git *' --allow 'ls *'`

---

## Custom system prompt

Replace the default "helpful assistant" system prompt with the contents of a file:

```bash
uio chat --system /path/to/my-system.txt
```

This is useful for domain-specific assistants — a security researcher prompt, a commit-message writer prompt, a code reviewer with specific rules, etc.

---

## Multi-turn history

The conversation accumulates across turns for the session lifetime. `/clear` resets the history back to empty — useful when the context has grown large or you are starting a different task.

History is held in memory only; it is not persisted between sessions.

---

## Session cost summary

When the session ends, uio prints a summary and writes a ledger entry:

```
Session ended.
  Session: 4,218 tokens (3,891 in / 327 out) — $0.000422
```

The entry is written to the cost ledger under agent name `"chat"`. See [Cost ledger](10-cost.md) to query it.

---

## Streaming implementation

Token streaming works differently per provider:

- **Gemini** — uses `generate_content_stream`; tokens arrive as parts in each chunk
- **OpenAI / Ollama** — uses `stream=True` with `stream_options: {include_usage: true}`; tokens arrive as delta content; usage metadata is included in the final chunk

If a streaming error occurs, the REPL falls back to a non-streaming request automatically and prints a warning.

Keyboard interrupt (Ctrl-C) during a response cancels the current turn without exiting the session.

---

## Examples

```bash
# Minimal — auto-selects provider
uio chat

# Force Ollama for offline use
uio chat --provider ollama

# Enable tools with pre-approved git read commands
uio chat --tools --allow 'git *'

# Use a project-specific system prompt
uio chat --system .uio/chat-system.txt

# Enable tools but block any rm command
uio chat --tools --deny 'rm *' --deny 'sudo *'

# Fully automated (no prompts)
uio chat --auto-approve --provider gemini
```
