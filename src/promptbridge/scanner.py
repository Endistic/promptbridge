"""Light repo scan: stack, test framework, top-level layout. Reads manifests only."""

from __future__ import annotations

import json
import re
from pathlib import Path

_SKIP_DIRS = {"node_modules", "venv", ".venv", "dist", "build", "__pycache__", "target", ".dart_tool", "vendor"}

_JS_DEPS = {
    "react": "React", "next": "Next.js", "vue": "Vue", "svelte": "Svelte", "@angular/core": "Angular",
    "express": "Express", "@nestjs/core": "NestJS", "typescript": "TypeScript", "vite": "Vite",
    "tailwindcss": "Tailwind CSS", "react-native": "React Native", "electron": "Electron",
    "prisma": "Prisma", "@reduxjs/toolkit": "Redux Toolkit", "zustand": "Zustand",
}
_JS_TESTS = {"jest": "Jest", "vitest": "Vitest", "@playwright/test": "Playwright", "cypress": "Cypress", "mocha": "Mocha"}
_PY_DEPS = {
    "fastapi": "FastAPI", "django": "Django", "flask": "Flask", "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic", "pandas": "pandas", "numpy": "NumPy", "polars": "Polars",
    "celery": "Celery", "airflow": "Airflow", "torch": "PyTorch", "streamlit": "Streamlit",
}
_PY_TESTS = {"pytest": "pytest"}


def _read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _scan_dir(d: Path, stack: set[str], tests: set[str]) -> None:
    pkg = d / "package.json"
    if pkg.exists():
        try:
            data = json.loads(_read(pkg))
        except json.JSONDecodeError:
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        stack.add("JavaScript/Node")
        for k, name in _JS_DEPS.items():
            if k in deps:
                stack.add(name)
        for k, name in _JS_TESTS.items():
            if k in deps:
                tests.add(name)

    py_text = "".join(_read(d / f).lower() for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"))
    if py_text:
        stack.add("Python")
        for k, name in _PY_DEPS.items():
            if re.search(rf"(^|[^a-z0-9_-]){re.escape(k)}([^a-z0-9_-]|$)", py_text):
                stack.add(name)
        for k, name in _PY_TESTS.items():
            if k in py_text:
                tests.add(name)

    pub = d / "pubspec.yaml"
    if pub.exists():
        stack.update({"Dart", "Flutter"} if "flutter" in _read(pub) else {"Dart"})
        if "flutter_test" in _read(pub):
            tests.add("flutter_test")

    for marker, name in (("go.mod", "Go"), ("Cargo.toml", "Rust"), ("pom.xml", "Java/Maven"),
                         ("build.gradle", "JVM/Gradle"), ("build.gradle.kts", "Kotlin/Gradle"),
                         ("Gemfile", "Ruby"), ("composer.json", "PHP"), ("Dockerfile", "Docker"),
                         ("docker-compose.yml", "Docker Compose"), ("compose.yaml", "Docker Compose")):
        if (d / marker).exists():
            stack.add(name)


def scan(root: Path | None) -> dict:
    if root is None or not root.is_dir():
        return {"root": None, "stack": [], "test_frameworks": [], "top_level": []}
    stack: set[str] = set()
    tests: set[str] = set()
    _scan_dir(root, stack, tests)

    top_level = []
    for child in sorted(root.iterdir()):
        if child.name.startswith(".") or child.name in _SKIP_DIRS:
            continue
        top_level.append(child.name + ("/" if child.is_dir() else ""))
    # Monorepos: look one level down for more manifests.
    for child in [c for c in root.iterdir() if c.is_dir()][:40]:
        if not child.name.startswith(".") and child.name not in _SKIP_DIRS:
            _scan_dir(child, stack, tests)

    return {
        "root": str(root),
        "stack": sorted(stack),
        "test_frameworks": sorted(tests),
        "top_level": top_level[:60],
    }
