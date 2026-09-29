"""Glossary: maps the words a user says to the real names in their codebase.

Two scopes:
  personal — in the user's SQLite db, follows them across repos
  repo     — in <repo>/.promptbridge/glossary.yaml, committed and shared by the team
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .store import Store

REPO_FILE = Path(".promptbridge") / "glossary.yaml"
KINDS = ("code_symbol", "domain_term", "path")


def find_repo_root(cwd: str | None) -> Path | None:
    if not cwd:
        return None
    p = Path(cwd).expanduser().resolve()
    if not p.exists():
        return None
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return p


def load_repo_glossary(root: Path | None) -> list[dict]:
    if root is None:
        return []
    f = root / REPO_FILE
    if not f.exists():
        return []
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    out = []
    for e in data.get("terms", []):
        if e.get("native") and e.get("en"):
            out.append({
                "term_native": str(e["native"]),
                "term_en": str(e["en"]),
                "kind": e.get("kind", "domain_term"),
                "scope": "repo",
            })
    return out


def save_repo_term(root: Path, term_native: str, term_en: str, kind: str) -> dict:
    f = root / REPO_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    data = (yaml.safe_load(f.read_text(encoding="utf-8")) if f.exists() else None) or {}
    terms = [t for t in data.get("terms", []) if not (t.get("native") == term_native and t.get("en") == term_en)]
    terms.append({"native": term_native, "en": term_en, "kind": kind})
    data["terms"] = sorted(terms, key=lambda t: t["native"])
    header = "# promptbridge repo glossary — the team's words → names in this codebase\n"
    f.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"term_native": term_native, "term_en": term_en, "kind": kind, "scope": "repo", "file": str(f)}


def remove_repo_term(root: Path, term_native: str, term_en: str | None) -> int:
    f = root / REPO_FILE
    if not f.exists():
        return 0
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    before = data.get("terms", [])
    after = [t for t in before if not (t.get("native") == term_native and (term_en is None or t.get("en") == term_en))]
    data["terms"] = after
    f.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return len(before) - len(after)


def all_terms(store: Store, root: Path | None) -> list[dict]:
    # Repo terms win over personal ones with the same native word.
    repo = load_repo_glossary(root)
    repo_natives = {t["term_native"].casefold() for t in repo}
    personal = [t for t in store.glossary_all() if t["term_native"].casefold() not in repo_natives]
    return repo + personal


def match(text: str, terms: list[dict]) -> list[dict]:
    """Longest-first, non-overlapping substring match.

    Thai has no spaces between words, so tokenizing is unreliable; substring
    matching against a known vocabulary is exact enough for a glossary of a few
    hundred entries.
    """
    lowered = text.casefold()
    taken = [False] * len(lowered)
    hits: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for t in sorted(terms, key=lambda t: len(t["term_native"]), reverse=True):
        needle = t["term_native"].casefold()
        if not needle:
            continue
        for m in re.finditer(re.escape(needle), lowered):
            s, e = m.span()
            if any(taken[s:e]):
                continue
            for i in range(s, e):
                taken[i] = True
            key = (t["term_native"], t["term_en"])
            if key not in seen:
                seen.add(key)
                hits.append({k: t[k] for k in ("term_native", "term_en", "kind", "scope") if k in t} | (
                    {"id": t["id"]} if "id" in t else {}
                ))
    return hits


_IDENT_PATTERNS = [
    re.compile(r"`([^`\n]{2,80})`"),
    re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b"),  # CamelCase
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),  # snake_case
    re.compile(r"\b[\w\-]+(?:/[\w\-.]+)+\.\w{1,5}\b"),  # paths with extension
]


def identifiers(text: str) -> set[str]:
    out: set[str] = set()
    for pat in _IDENT_PATTERNS:
        for m in pat.finditer(text):
            out.add((m.group(1) if m.groups() else m.group(0)).strip())
    return out


def candidates_from_edit(compiled: str, final: str, known_en: set[str]) -> list[str]:
    """Identifiers the user introduced when editing the spec — likely names the glossary should learn."""
    new = identifiers(final) - identifiers(compiled)
    return sorted(i for i in new if i not in known_en)
