# Releasing

Steps only the repository owner can do (they need the `Endistic` GitHub account and a PyPI account). Steps 1–2 are one-time setup; every later release is just step 3.

## 1. Create the GitHub repository and push

1. On GitHub: **New repository** → name `promptbridge` → **Public** → do *not* add a README, license or .gitignore (the project has them).
2. In the project folder:

```bash
cd ~/Language-Trans/promptbridge
git init -b main          # skip if the folder already has git history
git add -A
git commit -m "promptbridge 0.2.0"
git remote add origin https://github.com/Endistic/promptbridge.git
git push -u origin main
```

3. Check the **Actions** tab: the CI workflow should pass on all 8 jobs.
4. **Settings → Security → Private vulnerability reporting → Enable** (SECURITY.md relies on it).

## 2. Connect PyPI (trusted publishing — no API token stored anywhere)

1. Create or log in to your account at [pypi.org](https://pypi.org) and turn on 2FA.
2. Go to **Your account → Publishing → Add a new pending publisher** and enter:
   - PyPI project name: `promptbridge-mcp`
   - Owner: `Endistic`
   - Repository name: `promptbridge`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. On GitHub: **Settings → Environments → New environment** → name it `pypi`. (Optional: add yourself as a required reviewer so every release waits for your click.)

## 3. Release

For the first release (0.2.0) the version is already set — skip to step 3.3.

1. Move the **Unreleased** notes in `CHANGELOG.md` under a new version heading.
2. Bump `version` in `pyproject.toml`, `src/promptbridge/__init__.py` and `.claude-plugin/plugin.json` to the same number, then commit: `git commit -am "Release X.Y.Z"`.
3. Tag and push:

```bash
git tag v0.2.0
git push origin main --tags
```

The **Release** workflow checks that the tag matches `pyproject.toml`, runs the tests, builds, and publishes to PyPI. A few minutes later:

```bash
uvx promptbridge-mcp        # should start and wait silently; Ctrl+C to exit
```

4. On GitHub: **Releases → Draft a new release** → choose the tag → paste the changelog section → Publish.

## After the first release

Switch your own setup from the local folder to the published package:

```bash
claude mcp remove promptbridge -s user
claude mcp add promptbridge -s user -- uvx promptbridge-mcp
```

In Claude Desktop, change `"args"` to `["promptbridge-mcp"]`.
