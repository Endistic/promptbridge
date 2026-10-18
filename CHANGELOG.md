# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0]

### Added
- Native question phrasing for **Japanese, Mandarin Chinese (Simplified), Spanish, Russian, Arabic, French and Korean**, plus **English (UK)** and **English (Australia)** variants — 11 locales in total with Thai and English.
- Regional locale codes: `en-GB`, `en-AU`, `es-MX`, `zh-CN`, … are normalized (`en_gb`, `en-UK`, `jp`, `kr`, `zh-Hans` also work). A region without its own file inherits its base language; a region file only overrides what differs.
- A per-locale writing `style` (register, script, spelling) appended to the instructions the host model receives.
- Task-type keywords in all 11 languages.
- Traditional Chinese (`zh-TW`, `zh-HK`) falls back to English phrasing with an explicit Traditional-characters instruction instead of serving Simplified questions.
- `tests/test_locales.py`: every locale has every question, none left in English, task-type guessing per language.

### Changed
- `pb_capture` reports the normalized code (`ja-JP`, `en-GB`) and the language's English name.

## [0.2.0] — first public release

### Changed
- Published on PyPI as **`promptbridge-mcp`** (the name `promptbridge` is taken). Install with `uvx promptbridge-mcp`. The import package and the `promptbridge` command are unchanged; a `promptbridge-mcp` command alias is added.
- README is now in English; the Thai README moved to `README.th.md`.

### Added
- CI on Python 3.10–3.13 (Linux, macOS) and tag-triggered PyPI release via trusted publishing.
- CONTRIBUTING, Code of Conduct, Security policy, issue and pull request templates.

### Fixed
- Plugin server config moved from a root `.mcp.json` into `.claude-plugin/plugin.json`, so opening the repo in Claude Code no longer starts a broken project-level server.

## [0.1.1]

### Changed
- **Breaking:** tool argument `session_id` renamed to `spec_id` in `pb_clarify`, `pb_compile` and `pb_save`, and `pb_capture` now returns `spec_id`. Some MCP bridges strip arguments named `session_id`, which made these tools fail when proxied.

## [0.1.0]

### Added
- MCP server with six tools: `pb_capture`, `pb_clarify`, `pb_compile`, `pb_save`, `pb_glossary`, `pb_library`.
- Task types `bug_fix`, `feature`, `refactor`, `test`, `explain`.
- Thai and English question phrasing; other languages fall back to English phrasing translated by the host model.
- Personal (SQLite) and repo (YAML) glossary; spec library.
- `/spec` skill for Claude Code.
