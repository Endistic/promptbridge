import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own database, and the server's cached store is reset."""
    monkeypatch.setenv("PROMPTBRIDGE_HOME", str(tmp_path / "home"))
    from promptbridge import server

    server._store = None
    yield tmp_path
    server._store = None


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "shop"
    (r / ".git").mkdir(parents=True)
    (r / "api" / "auth").mkdir(parents=True)
    (r / "web" / "src").mkdir(parents=True)
    (r / "pyproject.toml").write_text('[project]\ndependencies = ["fastapi", "sqlalchemy"]\n[project.optional-dependencies]\ndev=["pytest"]\n')
    (r / "web" / "package.json").write_text('{"dependencies": {"react": "18"}, "devDependencies": {"vitest": "1", "typescript": "5"}}')
    return r
