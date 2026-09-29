"""Decides which questions to ask. Deterministic: no model calls here.

Order of candidates:
  1. required slots that are missing
  2. high-risk slots the host only inferred (ask to confirm)
  3. medium/high-risk optional slots that are missing — only to fill the
     remaining quota of a round that is already asking tier 1 or 2

A round asks at most MAX_QUESTIONS. After MAX_ROUNDS the spec compiles anyway
and anything still open becomes a visible assumption.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Locale, Question, SlotSpec, SlotValue, TaskTemplate

MAX_QUESTIONS = 3
MAX_ROUNDS = 2


@dataclass
class ClarifyResult:
    ready: bool
    questions: list[Question]
    reason: str
    open_slots: list[str] = field(default_factory=list)  # will become assumptions if compiled now
    warnings: list[str] = field(default_factory=list)


def effective(spec: SlotSpec, sv: SlotValue | None) -> str:
    """stated | inferred | default | missing"""
    if sv is None or sv.is_empty() or sv.status == "missing":
        return "default" if spec.default is not None else "missing"
    return sv.status


def normalize_slots(template: TaskTemplate, slots: dict[str, SlotValue]) -> tuple[dict[str, SlotValue], list[str]]:
    """Drop unknown slots (with a warning) and coerce text/list shapes."""
    warnings: list[str] = []
    out: dict[str, SlotValue] = {}
    for name, sv in slots.items():
        spec = template.slots.get(name)
        if spec is None:
            warnings.append(f"Unknown slot {name!r} for task_type {template.task_type!r}; ignored.")
            continue
        v = sv.value_en
        if spec.kind == "list" and isinstance(v, str) and v.strip():
            v = [v.strip()]
        elif spec.kind == "text" and isinstance(v, list):
            v = "; ".join(str(x).strip() for x in v if str(x).strip())
        out[name] = SlotValue(value_en=v, status=sv.status)
    return out, warnings


def _question(spec: SlotSpec, kind: str, locale: Locale, sv: SlotValue | None) -> Question:
    if kind == "confirm":
        value = sv.value_en if sv else ""
        shown = "; ".join(value) if isinstance(value, list) else (value or "")
        prompt = locale.confirm.format(value=shown)
    else:
        prompt = locale.questions.get(spec.name, spec.description)
    return Question(
        slot=spec.name,
        kind=kind,  # type: ignore[arg-type]
        prompt=prompt,
        slot_description=spec.description,
        slot_kind=spec.kind,
        current_value=sv.value_en if sv else None,
    )


def open_slots(template: TaskTemplate, slots: dict[str, SlotValue]) -> list[str]:
    """Slots that would be surfaced as assumptions if compiled now."""
    result = []
    for name, spec in template.slots.items():
        state = effective(spec, slots.get(name))
        if state == "missing" and spec.required:
            result.append(name)
        elif state == "inferred" and spec.risk == "high":
            result.append(name)
    return result


def select_questions(
    template: TaskTemplate,
    slots: dict[str, SlotValue],
    locale: Locale,
    rounds_done: int,
    quick: bool = False,
) -> ClarifyResult:
    slots, warnings = normalize_slots(template, slots)
    still_open = open_slots(template, slots)

    if not template.ask:
        return ClarifyResult(True, [], f"{template.task_type} never asks questions", still_open, warnings)
    if quick:
        return ClarifyResult(True, [], "user asked to skip questions", still_open, warnings)
    if rounds_done >= MAX_ROUNDS:
        return ClarifyResult(True, [], f"reached {MAX_ROUNDS} rounds", still_open, warnings)

    tier1, tier2, tier3 = [], [], []
    for name, spec in template.slots.items():
        sv = slots.get(name)
        state = effective(spec, sv)
        if state == "missing" and spec.required:
            tier1.append(_question(spec, "missing", locale, sv))
        elif state == "inferred" and spec.risk == "high":
            tier2.append(_question(spec, "confirm", locale, sv))
        elif state == "missing" and not spec.required and spec.risk in ("high", "medium"):
            tier3.append(_question(spec, "missing", locale, sv))

    blocking = tier1 + tier2
    if not blocking:
        return ClarifyResult(True, [], "no required or high-risk gaps", [], warnings)

    # High-risk optional gaps before medium ones.
    tier3.sort(key=lambda q: 0 if template.slots[q.slot].risk == "high" else 1)
    questions = (blocking + tier3)[:MAX_QUESTIONS]
    return ClarifyResult(False, questions, f"{len(blocking)} blocking gap(s)", still_open, warnings)
