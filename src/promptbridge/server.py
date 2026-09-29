"""promptbridge MCP server.

The host model (Claude in Claude Code, Cursor, …) does the language work:
it reads the user's native-language request, fills slots in English and
phrases questions in the user's language. This server owns the structure:
templates, which questions to ask, the rendered spec, and memory.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

import functools

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[no-redef]

from . import __version__
from .catalog import get_template, guess_task_type, load_locale, load_templates
from .clarify import MAX_ROUNDS, normalize_slots, select_questions
from .glossary import (
    KINDS,
    all_terms,
    candidates_from_edit,
    find_repo_root,
    match,
    remove_repo_term,
    save_repo_term,
)
from .models import Outcome, SlotValue
from .render import compile_spec
from .scanner import scan
from .store import Store

mcp = _Server(
    "promptbridge",
    instructions=(
        "promptbridge turns a request written in the user's own language into a structured English "
        "task spec for a coding agent. Flow: pb_capture → fill slots in English → pb_clarify (ask the "
        "returned questions in the user's language, max 2 rounds) → pb_compile → show the user a short "
        "summary in their language → on approval, carry out the spec → pb_save the outcome."
    ),
)

_store: Store | None = None


def tool(fn):
    """Register a tool; ValueError becomes ToolError so the host model sees the message."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    return mcp.tool()(wrapper)


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _slot_schema(task_type: str) -> list[dict]:
    t = get_template(task_type)
    return [
        {
            "name": s.name,
            "description": s.description,
            "kind": s.kind,
            "required": s.required,
            "risk": s.risk,
            "has_default": s.default is not None,
        }
        for s in t.slots.values()
    ]


def _parse_slots(slots: dict[str, Any] | None) -> dict[str, SlotValue]:
    out: dict[str, SlotValue] = {}
    for k, v in (slots or {}).items():
        out[k] = v if isinstance(v, SlotValue) else SlotValue.model_validate(v)
    return out


@tool
def pb_capture(
    raw_text: str,
    locale: str = "th",
    cwd: Optional[str] = None,
    task_type: Optional[str] = None,
) -> dict:
    """Start a session from the user's request, written in their own language.

    Returns a session_id, a guessed task_type (override it if wrong), glossary terms found in the
    text, a light scan of the repo at `cwd`, and the slot schema to fill.

    Next: read raw_text, fill every slot you can as ENGLISH text (value_en) with status
    "stated" (the user said it) or "inferred" (you guessed it from context or the code), leave the
    rest out, then call pb_clarify.
    """
    if not raw_text.strip():
        raise ValueError("raw_text is empty.")
    loc = load_locale(locale)
    guessed, scores = guess_task_type(raw_text)
    chosen = task_type or guessed
    get_template(chosen)  # validate

    root = find_repo_root(cwd)
    repo_context = scan(root)
    hits = match(raw_text, all_terms(store(), root))
    store().glossary_bump([h["id"] for h in hits if "id" in h])

    context = {"repo": repo_context, "glossary_hits": [{k: v for k, v in h.items() if k != "id"} for h in hits]}
    sid = store().create_session(loc.locale, raw_text, str(root) if root else cwd, chosen, context)

    return {
        "session_id": sid,
        "task_type": chosen,
        "task_type_guess": guessed,
        "task_type_scores": scores,
        "task_types": {k: t.title for k, t in load_templates().items()},
        "locale": {"code": loc.locale, "language": loc.name, "phrasing_available": not loc.is_fallback},
        "glossary_hits": context["glossary_hits"],
        "repo_context": repo_context,
        "slot_schema": _slot_schema(chosen),
        "next_step": (
            "Fill slots in English from raw_text (use glossary term_en names; inspect the repo if it helps "
            "fill `files`). Call pb_clarify with {slot: {value_en, status}}. If the task_type guess is wrong, "
            "pass the right task_type to pb_clarify."
        ),
    }


@tool
def pb_clarify(
    session_id: str,
    slots: dict[str, SlotValue],
    task_type: Optional[str] = None,
    quick: bool = False,
) -> dict:
    """Decide whether the spec is clear enough, and if not, which questions to ask (max 3, max 2 rounds).

    `slots` is the full current state: {name: {"value_en": str | [str], "status": "stated"|"inferred"}}.
    After the user answers, translate their answers to English, update the slots (status "stated")
    and call pb_clarify again. Set quick=true if the user wants to skip questions.

    Each returned question has a default `prompt` in the user's language. Ask it in that language,
    adapted to this task, and offer 2-4 concrete options plus a free-text choice. For kind="confirm",
    show your inferred value and ask the user to confirm or correct it.
    """
    sess = store().get_session(session_id)
    if task_type and task_type != sess["task_type"]:
        get_template(task_type)
        store().update_session(session_id, task_type=task_type, rounds=0)
        sess["task_type"], sess["rounds"] = task_type, 0

    template = get_template(sess["task_type"])
    loc = load_locale(sess["locale"])
    parsed = _parse_slots(slots)
    result = select_questions(template, parsed, loc, sess["rounds"], quick=quick)

    clean, _ = normalize_slots(template, parsed)
    rounds = sess["rounds"] + (0 if result.ready else 1)
    store().update_session(
        session_id, slots={k: v.model_dump() for k, v in clean.items()}, rounds=rounds
    )

    out = {
        "ready": result.ready,
        "reason": result.reason,
        "round": rounds,
        "max_rounds": MAX_ROUNDS,
        "questions": [q.model_dump() for q in result.questions],
        "open_slots": result.open_slots,
        "warnings": result.warnings,
    }
    if loc.is_fallback and result.questions:
        out["translate_questions_to"] = loc.name
    out["next_step"] = (
        "Call pb_compile." if result.ready else
        f"Ask these questions in {loc.name}, update slots with the answers (in English), call pb_clarify again."
    )
    return out


@tool
def pb_compile(session_id: str, slots: Optional[dict[str, SlotValue]] = None) -> dict:
    """Render the English task spec from the slots (uses the last slots sent to pb_clarify if omitted).

    Anything not confirmed becomes a visible Assumption in the spec. Show the user a short summary in
    their language (see summary_instruction) and ask them to approve, edit, or cancel before acting.
    """
    sess = store().get_session(session_id)
    template = get_template(sess["task_type"])
    loc = load_locale(sess["locale"])
    parsed = _parse_slots(slots) if slots is not None else _parse_slots(sess["slots"])
    ctx = sess["context"]

    result = compile_spec(template, parsed, loc, ctx.get("repo"), ctx.get("glossary_hits"))
    clean, _ = normalize_slots(template, parsed)
    store().update_session(
        session_id, slots={k: v.model_dump() for k, v in clean.items()}, spec=result.spec_markdown
    )
    return {
        "spec_markdown": result.spec_markdown,
        "summary_instruction": loc.summary_instruction.strip(),
        "reflect_instruction": loc.reflect_instruction.strip(),
        "validation": {
            "missing_required": result.missing_required,
            "assumptions": result.assumptions,
            "warnings": result.warnings,
        },
        "next_step": (
            "Show the summary and wait for approve/edit/cancel. On approve, carry out spec_markdown as your "
            "task. Afterwards call pb_save with the outcome (and final_spec if the user edited it)."
        ),
    }


@tool
def pb_save(session_id: str, outcome: Outcome, final_spec: Optional[str] = None) -> dict:
    """Record how the spec was received: accepted, edited (pass final_spec), or rejected.

    Accepted and edited specs go into the library. For edited specs, returns identifiers the user
    added — pair each with the word the user used in raw_text, confirm with the user, then add the
    pairs with pb_glossary.
    """
    sess = store().get_session(session_id)
    compiled = sess.get("spec") or ""
    if outcome == "edited" and not final_spec:
        raise ValueError("outcome 'edited' needs final_spec (the spec as the user changed it).")

    store().update_session(session_id, outcome=outcome, final_spec=final_spec)
    lib_id = None
    if outcome != "rejected" and (final_spec or compiled):
        lib_id = store().library_add(
            session_id, sess["task_type"], sess["locale"], sess["raw_text"], final_spec or compiled, outcome
        )

    candidates: list[str] = []
    if outcome == "edited" and final_spec:
        root = find_repo_root(sess["cwd"])
        known = {t["term_en"] for t in all_terms(store(), root)}
        candidates = candidates_from_edit(compiled, final_spec, known)

    return {
        "saved": True,
        "library_id": lib_id,
        "glossary_candidates": candidates,
        "raw_text": sess["raw_text"] if candidates else None,
        "next_step": (
            "For each candidate, find the word the user used for it in raw_text, ask the user to confirm the "
            "pair, then call pb_glossary(action='add')." if candidates else "Done."
        ),
    }


@tool
def pb_glossary(
    action: Literal["list", "add", "remove"],
    term_native: Optional[str] = None,
    term_en: Optional[str] = None,
    kind: Literal["code_symbol", "domain_term", "path"] = "domain_term",
    scope: Literal["personal", "repo"] = "personal",
    cwd: Optional[str] = None,
) -> dict:
    """Manage the glossary that maps the user's words to real names in the code.

    personal scope lives in the user's local database; repo scope lives in
    <repo>/.promptbridge/glossary.yaml so a team can commit and share it (needs cwd).
    """
    root = find_repo_root(cwd)
    if action == "list":
        return {"terms": [{k: v for k, v in t.items() if k in ("term_native", "term_en", "kind", "scope", "uses")}
                          for t in all_terms(store(), root)]}

    if not term_native:
        raise ValueError("term_native is required for add/remove.")
    if scope == "repo" and root is None:
        raise ValueError("scope='repo' needs cwd pointing inside the repository.")

    if action == "add":
        if not term_en:
            raise ValueError("term_en is required for add.")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        entry = (save_repo_term(root, term_native, term_en, kind) if scope == "repo"  # type: ignore[arg-type]
                 else store().glossary_add(term_native, term_en, kind, "manual"))
        return {"added": entry}

    removed = (remove_repo_term(root, term_native, term_en) if scope == "repo"  # type: ignore[arg-type]
               else store().glossary_remove(term_native, term_en))
    return {"removed": removed}


@tool
def pb_library(
    query: str = "",
    task_type: Optional[str] = None,
    limit: int = 5,
    library_id: Optional[int] = None,
) -> dict:
    """Search specs that worked before (accepted or edited), to reuse or adapt.

    Pass library_id to get one spec in full.
    """
    if library_id is not None:
        item = store().library_get(library_id)
        if item is None:
            raise ValueError(f"No library entry {library_id}.")
        return {"spec": item}
    rows = store().library_search(query, task_type, max(1, min(limit, 20)))
    return {
        "results": [
            {
                "library_id": r["id"],
                "task_type": r["task_type"],
                "outcome": r["outcome"],
                "raw_text": r["raw_text"][:200],
                "spec_preview": r["spec"][:300],
            }
            for r in rows
        ]
    }


@mcp.resource("promptbridge://stats")
def stats() -> dict:
    """Session outcomes so far — accepted vs edited vs rejected."""
    return {"version": __version__, "outcomes": store().outcome_stats()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
