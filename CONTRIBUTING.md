# Contributing to promptbridge

Thanks for helping. Issues and pull requests are welcome in English or Thai — write in whatever language you think in; that is the point of this project.

## Dev setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
git clone https://github.com/<your-github-username>/promptbridge
cd promptbridge
uv venv
uv pip install -e ".[dev]"
.venv/bin/pytest -q
```

To try your local copy in Claude Code:

```bash
claude mcp add promptbridge-dev -s user -- uvx --from "$(pwd)" promptbridge
```

Restart Claude Code after each change so it starts the new server.

## Project layout

| Path | What lives there |
| --- | --- |
| `src/promptbridge/server.py` | MCP tools (`pb_*`) — thin wrappers |
| `src/promptbridge/clarify.py` | Which questions to ask. Deterministic, no model calls |
| `src/promptbridge/render.py` | Renders the English spec |
| `src/promptbridge/templates/*.yaml` | One file per task type |
| `src/promptbridge/locales/*.yaml` | Question phrasing per language |
| `src/promptbridge/glossary.py`, `store.py` | Glossary matching and SQLite storage |
| `skills/spec/SKILL.md` | The `/spec` skill for Claude Code |
| `tests/` | Unit tests and end-to-end tests through a real MCP client |

## Add a task type

1. Copy `src/promptbridge/templates/feature.yaml` to `<name>.yaml`.
2. Set `task_type`, `keywords` (per language), `slots` and `sections`.
   - `required: true` — asked whenever it is missing.
   - `risk: high` — confirmed whenever the model only guessed it.
   - `default:` — never asked; used when missing.
3. Add question phrasing for each new slot to every file in `locales/`.
4. Add a test in `tests/test_core.py`.

## Add a language

1. Copy `src/promptbridge/locales/en.yaml` to `<code>.yaml` (ISO 639-1, e.g. `ja.yaml`).
2. Translate `questions` and `confirm`. Keep `summary_instruction`, `reflect_instruction` and `communication_line` in English but replace `{language}` with the language name — they are instructions to the model.
3. Add your language's words to `keywords` in each template so task types are guessed correctly.
4. Run the tests. Open a PR — native speakers reviewing phrasing is the most valuable contribution this project can get.

## Rules for changes

- **Tool names and argument shapes are a public API.** Don't change them in a minor release. Never name an argument `session_id` — some MCP bridges strip it (see 0.1.1).
- Keep the server free of LLM calls and network access.
- No new runtime dependencies without discussing in an issue first.
- Every behavior change comes with a test.

## Pull requests

- One topic per PR. Describe the problem, not just the change.
- `pytest -q` must pass. CI runs Python 3.10–3.13 on Linux and macOS.
- Add a line under **Unreleased** in `CHANGELOG.md`.

By contributing you agree your work is released under the [MIT License](LICENSE) and that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).
