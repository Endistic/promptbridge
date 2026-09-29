"""SQLite storage: sessions, personal glossary, spec library."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    locale TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    cwd TEXT,
    task_type TEXT NOT NULL,
    rounds INTEGER NOT NULL DEFAULT 0,
    slots TEXT NOT NULL DEFAULT '{}',
    context TEXT NOT NULL DEFAULT '{}',
    spec TEXT,
    outcome TEXT,
    final_spec TEXT
);
CREATE TABLE IF NOT EXISTS glossary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_native TEXT NOT NULL,
    term_en TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'domain_term',
    source TEXT NOT NULL DEFAULT 'manual',
    uses INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    UNIQUE(term_native, term_en)
);
CREATE TABLE IF NOT EXISTS library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    task_type TEXT NOT NULL,
    locale TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    spec TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def default_home() -> Path:
    return Path(os.environ.get("PROMPTBRIDGE_HOME", Path.home() / ".promptbridge"))


class Store:
    def __init__(self, path: Path | str | None = None):
        if path is None:
            home = default_home()
            home.mkdir(parents=True, exist_ok=True)
            path = home / "pb.db"
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ---- sessions -------------------------------------------------------
    def create_session(self, locale: str, raw_text: str, cwd: str | None, task_type: str, context: dict) -> str:
        sid = uuid.uuid4().hex[:12]
        now = time.time()
        self.db.execute(
            "INSERT INTO sessions (id, created_at, updated_at, locale, raw_text, cwd, task_type, context)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (sid, now, now, locale, raw_text, cwd, task_type, json.dumps(context, ensure_ascii=False)),
        )
        self.db.commit()
        return sid

    def get_session(self, sid: str) -> dict:
        row = self.db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown session_id {sid!r}. Call pb_capture first.")
        d = dict(row)
        d["slots"] = json.loads(d["slots"])
        d["context"] = json.loads(d["context"])
        return d

    def update_session(self, sid: str, **fields) -> None:
        if not fields:
            return
        for k in ("slots", "context"):
            if k in fields:
                fields[k] = json.dumps(fields[k], ensure_ascii=False)
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(f"UPDATE sessions SET {cols} WHERE id = ?", (*fields.values(), sid))
        self.db.commit()

    def outcome_stats(self) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT COALESCE(outcome, 'open') AS o, COUNT(*) AS n FROM sessions GROUP BY o"
        ).fetchall()
        return {r["o"]: r["n"] for r in rows}

    # ---- glossary -------------------------------------------------------
    def glossary_all(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM glossary ORDER BY uses DESC, term_native").fetchall()
        return [dict(r) | {"scope": "personal"} for r in rows]

    def glossary_add(self, term_native: str, term_en: str, kind: str, source: str) -> dict:
        self.db.execute(
            "INSERT INTO glossary (term_native, term_en, kind, source, created_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT(term_native, term_en) DO UPDATE SET kind = excluded.kind",
            (term_native.strip(), term_en.strip(), kind, source, time.time()),
        )
        self.db.commit()
        row = self.db.execute(
            "SELECT * FROM glossary WHERE term_native = ? AND term_en = ?", (term_native.strip(), term_en.strip())
        ).fetchone()
        return dict(row) | {"scope": "personal"}

    def glossary_remove(self, term_native: str, term_en: str | None = None) -> int:
        if term_en:
            cur = self.db.execute(
                "DELETE FROM glossary WHERE term_native = ? AND term_en = ?", (term_native, term_en)
            )
        else:
            cur = self.db.execute("DELETE FROM glossary WHERE term_native = ?", (term_native,))
        self.db.commit()
        return cur.rowcount

    def glossary_bump(self, ids: list[int]) -> None:
        if ids:
            self.db.executemany("UPDATE glossary SET uses = uses + 1 WHERE id = ?", [(i,) for i in ids])
            self.db.commit()

    # ---- library --------------------------------------------------------
    def library_add(self, session_id: str, task_type: str, locale: str, raw_text: str, spec: str, outcome: str) -> int:
        cur = self.db.execute(
            "INSERT INTO library (session_id, task_type, locale, raw_text, spec, outcome, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (session_id, task_type, locale, raw_text, spec, outcome, time.time()),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def library_get(self, lib_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM library WHERE id = ?", (lib_id,)).fetchone()
        return dict(row) if row else None

    def library_search(self, query: str, task_type: str | None, limit: int) -> list[dict]:
        sql = "SELECT * FROM library"
        args: list = []
        if task_type:
            sql += " WHERE task_type = ?"
            args.append(task_type)
        sql += " ORDER BY created_at DESC LIMIT 500"
        rows = [dict(r) for r in self.db.execute(sql, args).fetchall()]
        q = query.casefold().strip()
        tokens = [t for t in q.split() if t]
        if not tokens:
            return rows[:limit]
        scored = []
        for r in rows:
            hay = (r["raw_text"] + "\n" + r["spec"]).casefold()
            score = sum(1 for t in tokens if t in hay) + (2 if q in hay else 0)
            if score:
                scored.append((score, r["created_at"], r))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [r for _, _, r in scored[:limit]]
