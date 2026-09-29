"""Renders the English task spec. Deterministic: the same slots give the same spec."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from jinja2 import Environment, StrictUndefined

from .clarify import effective, normalize_slots
from .models import Locale, SlotValue, TaskTemplate

_BASE = """\
{%- for s in sections %}
## {{ s.title }}
{% if s.style == "paragraph" -%}
{{ s.lines | join(" ") }}
{% elif s.style == "code" -%}
```
{{ s.lines | join("\\n") }}
```
{% else -%}
{% for item in s.lines -%}
{% if s.style == "bullets" %}- {{ item }}
{% elif s.style == "checklist" %}- [ ] {{ item }}
{% elif s.style == "numbered" %}{{ loop.index }}. {{ item }}
{% endif %}
{%- endfor %}
{%- endif %}
{%- if loop.first and context_lines %}
## Context
{% for line in context_lines %}- {{ line }}
{% endfor %}
{%- endif %}
{%- endfor %}
{%- if terminology %}
## Terminology
The user's words map to these names in the codebase. Use the names on the right.
{% for t in terminology %}- "{{ t.term_native }}" = `{{ t.term_en }}`
{% endfor %}
{%- endif %}
{%- if assumptions %}
## Assumptions
Not confirmed by the user. If one turns out wrong, stop and ask.
{% for a in assumptions %}- {{ a }}
{% endfor %}
{%- endif %}
## How to work
{% for i in instructions %}- {{ i }}
{% endfor %}"""

_env = Environment(undefined=StrictUndefined, keep_trailing_newline=False, trim_blocks=False)
_tmpl = _env.from_string(_BASE)


@dataclass
class CompileResult:
    spec_markdown: str
    missing_required: list[str]
    assumptions: list[str]
    warnings: list[str] = field(default_factory=list)


def _as_items(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(v).strip() for v in value if str(v).strip()]


def _non_latin(text: str) -> bool:
    """True if text contains letters outside Latin scripts — a sign the host forgot to translate."""
    for ch in text:
        if ch.isalpha() and ord(ch) > 0x24F:
            name = unicodedata.name(ch, "")
            if "LATIN" not in name:
                return True
    return False


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compile_spec(
    template: TaskTemplate,
    slots: dict[str, SlotValue],
    locale: Locale,
    repo_context: dict | None = None,
    glossary_hits: list[dict] | None = None,
) -> CompileResult:
    slots, warnings = normalize_slots(template, slots)
    missing_required: list[str] = []
    assumptions: list[str] = []

    title_of = {slot: sec.title for sec in template.sections for slot in sec.slots}
    inferred_titles: list[str] = []

    # Resolve each slot to the items that will be printed.
    resolved: dict[str, list[str]] = {}
    for name, spec in template.slots.items():
        sv = slots.get(name)
        state = effective(spec, sv)
        if state in ("stated", "inferred"):
            items = _as_items(sv.value_en)  # type: ignore[union-attr]
            if state == "inferred" and spec.risk in ("high", "medium") and name in title_of:
                if title_of[name] not in inferred_titles:
                    inferred_titles.append(title_of[name])
        elif state == "default":
            items = _as_items(spec.default)
        else:  # missing
            items = _as_items(spec.fallback)
            if spec.required:
                missing_required.append(name)
                assumptions.append(
                    f"Not specified: {spec.description} Choose a sensible option and state it before you start."
                )
        resolved[name] = [_clean(i) for i in items]
        for item in resolved[name]:
            if locale.locale != "en" and _non_latin(item):
                warnings.append(f"Slot {name!r} still contains untranslated text: {item[:60]!r}")

    if inferred_titles:
        assumptions.insert(0, "Inferred from context, not stated by the user: " + ", ".join(inferred_titles) + ".")

    sections = []
    for sec in template.sections:
        items = [i for slot in sec.slots for i in resolved.get(slot, [])]
        if items:
            sections.append({"title": sec.title, "style": sec.style, "lines": items})

    context_lines = []
    rc = repo_context or {}
    if rc.get("stack"):
        context_lines.append("Stack: " + ", ".join(rc["stack"]))
    if rc.get("test_frameworks"):
        context_lines.append("Tests: " + ", ".join(rc["test_frameworks"]))
    if resolved.get("files"):
        context_lines.append("Likely files: " + ", ".join(f"`{f}`" for f in resolved["files"]))

    instructions = list(template.instructions)
    instructions.append("If anything in this spec is ambiguous or conflicts with the code, ask before guessing.")
    if locale.locale != "en":
        instructions.append(_clean(locale.communication_line))

    md = _tmpl.render(
        sections=sections,
        context_lines=context_lines,
        terminology=glossary_hits or [],
        assumptions=assumptions,
        instructions=instructions,
    )
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return CompileResult(md, missing_required, assumptions, warnings)
