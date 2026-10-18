# Contributing to promptbridge

Thanks for helping. Issues and pull requests are welcome in English or Thai — write in whatever language you think in; that is the point of this project.

## Dev setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
git clone https://github.com/Endistic/promptbridge
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

1. Copy `src/promptbridge/locales/ja.yaml` to `<code>.yaml` (ISO 639-1, lowercase, e.g. `de.yaml`).
2. Translate every entry in `questions` and `confirm` (keep `{value}` in `confirm`). Set `name` (English name) and `native_name`.
3. Write `style` in **English**: one or two sentences telling the model how to write in your language — register (formal/informal), script, punctuation. It is appended to the instructions the model receives.
4. Add your language's words to `keywords` in each file in `templates/` so task types are guessed correctly. Matching is substring-based, so word stems work (`ошибк` matches `ошибка`, `ошибки`).
5. Add the code to `SHIPPED` and a sentence or two to `test_guess_task_type_per_language` in `tests/test_locales.py`, then run the tests. They check that no question is missing or left in English.

**A regional variant** (spelling, dates, vocabulary) is an overlay: `<base>-<region>.yaml` (e.g. `en-gb.yaml`, `pt-br.yaml`) containing only `name`, `style` and the questions that differ. Everything else is inherited from the base file. A variant in a different script (Traditional Chinese) belongs in `_SCRIPT_FALLBACK` in `catalog.py` until someone writes its full file.

Native speakers reviewing existing phrasing is the most valuable contribution this project can get.

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
