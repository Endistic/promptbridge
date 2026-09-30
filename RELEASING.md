# Releasing

Steps only the repository owner can do (they need your GitHub and PyPI accounts). The first release is a one-time setup; later releases are just step 4.

## 1. Replace the placeholder

Replace `<your-github-username>` with your GitHub username in:

- `pyproject.toml` (project URLs)
- `README.md`, `README.th.md`, `CONTRIBUTING.md` (install and clone commands)

```bash
grep -rl "<your-github-username>" . --exclude-dir=.venv | xargs sed -i '' 's/<your-github-username>/YOUR_NAME/g'   # macOS sed
```

## 2. Create the GitHub repository and push

1. On GitHub: **New repository** → name `promptbridge` → **Public** → do *not* add a README, license or .gitignore (the project has them).
2. In the project folder:

```bash
git init -b main          # skip if the folder already has git history
git add -A
git commit -m "promptbridge 0.2.0"
git remote add origin https://github.com/YOUR_NAME/promptbridge.git
git push -u origin main
```

3. Check the **Actions** tab: the CI workflow should pass on all 8 jobs.
4. **Settings → Security → Private vulnerability reporting → Enable** (SECURITY.md relies on it).

## 3. Connect PyPI (trusted publishing — no API token stored anywhere)

1. Create or log in to your account at [pypi.org](https://pypi.org) and turn on 2FA.
2. Go to **Your account → Publishing → Add a new pending publisher** and enter:
   - PyPI project name: `promptbridge-mcp`
   - Owner: `YOUR_NAME`
   - Repository name: `promptbridge`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. On GitHub: **Settings → Environments → New environment** → name it `pypi`. (Optional: add yourself as a required reviewer so every release waits for your click.)

## 4. Release

1. Move the **Unreleased** notes in `CHANGELOG.md` under a new version heading.
2. Bump `version` in `pyproject.toml`, `src/promptbridge/__init__.py` and `.claude-plugin/plugin.json` to the same number.
3. Commit, then tag and push:

```bash
git commit -am "Release 0.2.0"
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
