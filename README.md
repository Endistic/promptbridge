# promptbridge

**Type coding requests in your own language. Get a clear English task spec your AI coding agent can execute without guessing.**

[ภาษาไทย](README.th.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md)

Many developers read English fine but don't *think* in it fast enough to write precise prompts. promptbridge sits between you and your coding agent (Claude Code, Claude Desktop, Cursor, any MCP client):

```
/spec หน้า login อยากให้ถ้าใส่รหัสผิดหลายครั้งมันล็อคไว้ก่อน
      (login page: lock it after too many wrong passwords)
```

1. It asks **only what is ambiguous** — at most 3 tap-to-answer questions, in your language: *how many attempts? lock for how long? per account or per IP?*
2. It shows a **2–3 line summary in your language** plus the English spec: Goal · Context · Requirements · Constraints · Acceptance criteria · Assumptions.
3. You approve, and the agent does the work — **reporting back in your language**, with code, paths and errors left untouched.

It also learns your vocabulary: tell it once that «ตะกร้า» means `CartStore`, and every future spec uses the real name.

## How it works

| Part | Does |
| --- | --- |
| **Host model** (the Claude/LLM you already use) | Reads your language, fills spec slots in English, asks the questions, summarizes results |
| **promptbridge MCP server** (Python) | Task templates, decides which questions matter, renders the spec deterministically, remembers your glossary and specs that worked |

The server never calls an LLM itself — no extra API cost, no data leaves your machine. Everything is stored locally in `~/.promptbridge/`.

## Install

You need [uv](https://docs.astral.sh/uv/).

### Claude Code

```bash
# 1) Register the MCP server for all projects
claude mcp add promptbridge -s user -- uvx promptbridge-mcp

# 2) Install the /spec skill
mkdir -p ~/.claude/skills/spec
curl -fsSL https://raw.githubusercontent.com/Endistic/promptbridge/main/skills/spec/SKILL.md \
  -o ~/.claude/skills/spec/SKILL.md

# 3) In any project
/spec ปุ่มบันทึกในหน้าโปรไฟล์กดแล้วขึ้น error 500
```

### Claude Desktop

Claude menu (macOS menu bar) → **Settings… → Developer → Edit Config**, add the server, then quit (⌘Q) and reopen:

```json
{
  "mcpServers": {
    "promptbridge": { "command": "/opt/homebrew/bin/uvx", "args": ["promptbridge-mcp"] }
  }
}
```

Use the full path from `which uvx` — Claude Desktop does not see your shell's `PATH`. Then ask: *"Use promptbridge to make a spec for: …"*

### Cursor and other MCP clients

```json
{ "mcpServers": { "promptbridge": { "command": "uvx", "args": ["promptbridge-mcp"] } } }
```

Clients without the skill follow the workflow described in the tools themselves.

### From source

```bash
git clone https://github.com/Endistic/promptbridge
claude mcp add promptbridge -s user -- uvx --from ./promptbridge promptbridge
```

Or load it as a Claude Code plugin (server + skill): `claude --plugin-dir ./promptbridge`, then `/promptbridge:spec`.

## Usage

| Type | Result |
| --- | --- |
| `/spec <request>` | Full flow: ask → summarize → do |
| `/spec --quick <request>` | Skip questions; unknowns become visible Assumptions in the spec |
| "remember: ตะกร้า = CartStore" | Add a glossary term |
| "show my glossary" | List glossary terms |
| "have I asked for something like this before?" | Search specs that worked |

### Task types

`bug_fix` · `feature` · `refactor` · `test` · `explain` — each has its own required facts ([`src/promptbridge/templates/`](src/promptbridge/templates/)). Adding a type is one YAML file.

### Glossary

- **personal** — `~/.promptbridge/pb.db`, follows you across projects
- **repo** — `<repo>/.promptbridge/glossary.yaml`, commit it so the whole team shares one vocabulary

When you edit a spec and add a real name (e.g. `LoginAttemptService`), promptbridge offers to remember the pairing.

## Languages

Built around a `locale` from day one. Thai and English have hand-written question phrasing; any other language (Japanese, Vietnamese, Indonesian, Korean, Spanish, …) works today — the host model translates the questions. Adding native phrasing for a language is one file: [`src/promptbridge/locales/`](src/promptbridge/locales/). See [CONTRIBUTING.md](CONTRIBUTING.md#add-a-language).

## MCP tools

| Tool | Purpose |
| --- | --- |
| `pb_capture` | Start from the user's raw request: guess task type, match glossary, scan the repo |
| `pb_clarify` | Decide which questions to ask (max 3 per round, max 2 rounds) |
| `pb_compile` | Render the English spec; unconfirmed guesses become Assumptions |
| `pb_save` | Record accepted / edited / rejected; suggest glossary terms from edits |
| `pb_glossary` | List / add / remove terms (personal or repo scope) |
| `pb_library` | Search specs that worked before |

Resource `promptbridge://stats` reports accepted / edited / rejected counts.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `PROMPTBRIDGE_HOME` | `~/.promptbridge` | Where the local database lives |

Works with MCP Python SDK 1.x and 2.x.

## License

[MIT](LICENSE)
