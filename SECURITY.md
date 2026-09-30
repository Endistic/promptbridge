# Security Policy

## Supported versions

Only the latest release on PyPI (`promptbridge-mcp`) receives fixes.

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private reporting instead: **Security → Report a vulnerability** on this repository.

You can expect an acknowledgement within 7 days. Once a fix is released, the advisory is published with credit to the reporter unless you prefer otherwise.

## What promptbridge touches

- It runs locally as an MCP server over stdio and makes no network requests.
- It reads manifest files (`package.json`, `pyproject.toml`, …) in the directory the client passes as `cwd`.
- It writes to `~/.promptbridge/pb.db` (or `$PROMPTBRIDGE_HOME`) and, only when asked, to `<repo>/.promptbridge/glossary.yaml`.

Reports about reading or writing outside these locations are especially welcome.
