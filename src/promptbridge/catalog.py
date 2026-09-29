"""Loads task templates and locale files shipped with the package."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from .models import Locale, Section, SlotSpec, TaskTemplate

# Tie-break order when keyword scores are equal: the more specific type wins.
_PRIORITY = ["bug_fix", "explain", "test", "refactor", "feature"]

# Names for locales we have no phrasing file for yet. The server falls back to
# English phrasing and asks the host to translate.
LANGUAGE_NAMES = {
    "th": "Thai", "en": "English", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay", "es": "Spanish",
    "pt": "Portuguese", "fr": "French", "de": "German", "ru": "Russian",
    "ar": "Arabic", "hi": "Hindi", "tr": "Turkish", "it": "Italian", "pl": "Polish",
}


def _read_yaml(package: str, name: str) -> dict:
    text = resources.files(package).joinpath(name).read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


@lru_cache(maxsize=1)
def load_templates() -> dict[str, TaskTemplate]:
    pkg = "promptbridge.templates"
    common = _read_yaml(pkg, "_common.yaml").get("slots", {})
    out: dict[str, TaskTemplate] = {}
    for entry in resources.files(pkg).iterdir():
        if not entry.name.endswith(".yaml") or entry.name.startswith("_"):
            continue
        raw = _read_yaml(pkg, entry.name)
        merged = {**common, **raw.get("slots", {})}
        slots = {name: SlotSpec(name=name, **spec) for name, spec in merged.items()}
        sections = [Section(**s) for s in raw.get("sections", [])]
        # Common slots that no section mentions are rendered by the base template
        # (files → Context); make sure every section slot actually exists.
        for s in sections:
            for slot in s.slots:
                if slot not in slots:
                    raise ValueError(f"{entry.name}: section {s.title!r} uses unknown slot {slot!r}")
        out[raw["task_type"]] = TaskTemplate(
            task_type=raw["task_type"],
            title=raw.get("title", raw["task_type"]),
            ask=raw.get("ask", True),
            keywords=raw.get("keywords", {}),
            slots=slots,
            sections=sections,
            instructions=raw.get("instructions", []),
        )
    return out


def get_template(task_type: str) -> TaskTemplate:
    templates = load_templates()
    if task_type not in templates:
        raise ValueError(f"Unknown task_type {task_type!r}. Valid: {', '.join(sorted(templates))}")
    return templates[task_type]


def guess_task_type(text: str) -> tuple[str, dict[str, int]]:
    """Cheap keyword guess. The host model may override it."""
    lowered = text.casefold()
    scores: dict[str, int] = {}
    for t in load_templates().values():
        score = 0
        for words in t.keywords.values():
            for w in words:
                if w.casefold() in lowered:
                    score += 1
        scores[t.task_type] = score
    best = max(scores.values(), default=0)
    if best == 0:
        return "feature", scores
    for t in _PRIORITY:
        if scores.get(t) == best:
            return t, scores
    return max(scores, key=scores.__getitem__), scores


def language_name(code: str) -> str:
    base = code.split("-")[0].split("_")[0].lower()
    return LANGUAGE_NAMES.get(base, code)


@lru_cache(maxsize=32)
def load_locale(code: str) -> Locale:
    base = code.split("-")[0].split("_")[0].lower()
    pkg = "promptbridge.locales"
    available = {p.name[:-5] for p in resources.files(pkg).iterdir() if p.name.endswith(".yaml")}
    is_fallback = base not in available
    raw = _read_yaml(pkg, f"{'en' if is_fallback else base}.yaml")
    lang = language_name(base)
    for key in ("summary_instruction", "reflect_instruction", "communication_line"):
        raw[key] = raw[key].replace("{language}", lang)
    raw["locale"] = base
    raw["name"] = lang
    if is_fallback:
        raw["native_name"] = lang
    return Locale(**raw, is_fallback=is_fallback)
