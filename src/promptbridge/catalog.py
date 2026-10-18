"""Loads task templates and locale files shipped with the package."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from .models import Locale, Section, SlotSpec, TaskTemplate

# Tie-break order when keyword scores are equal: the more specific type wins.
_PRIORITY = ["bug_fix", "explain", "test", "refactor", "feature"]

# English names, used in instructions to the host model ("Reply in {language}").
LANGUAGE_NAMES = {
    "th": "Thai", "en": "English", "ja": "Japanese", "ko": "Korean", "zh": "Mandarin Chinese",
    "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay", "es": "Spanish",
    "pt": "Portuguese", "fr": "French", "de": "German", "ru": "Russian",
    "ar": "Arabic", "hi": "Hindi", "tr": "Turkish", "it": "Italian", "pl": "Polish",
    "nl": "Dutch", "uk": "Ukrainian", "he": "Hebrew", "fa": "Persian", "bn": "Bengali",
}

# Regional variants that change how the model should write.
REGION_NAMES = {
    "en-US": "English (US)", "en-GB": "English (UK)", "en-AU": "English (Australia)",
    "en-CA": "English (Canada)", "en-NZ": "English (New Zealand)", "en-IN": "English (India)",
    "zh-CN": "Mandarin Chinese (Simplified)", "zh-SG": "Mandarin Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional, Taiwan)", "zh-HK": "Chinese (Traditional, Hong Kong)",
    "zh-MO": "Chinese (Traditional, Macau)",
    "es-ES": "Spanish (Spain)", "es-MX": "Spanish (Mexico)", "pt-BR": "Portuguese (Brazil)",
    "pt-PT": "Portuguese (Portugal)", "fr-CA": "French (Canada)",
}

# Variants whose base phrasing file is in the wrong script: use English phrasing
# and ask the host to translate, with a writing-style hint.
_SCRIPT_FALLBACK = {
    "zh-TW": "Use Traditional Chinese characters (Taiwan usage).",
    "zh-HK": "Use Traditional Chinese characters (Hong Kong usage).",
    "zh-MO": "Use Traditional Chinese characters.",
}

_ALIASES = {"jp": "ja", "kr": "ko", "cn": "zh", "iw": "he", "zh-hans": "zh-cn", "zh-hant": "zh-tw"}

_INSTRUCTION_KEYS = ("summary_instruction", "reflect_instruction", "communication_line")


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


def normalize_locale(code: str | None) -> str:
    """'th' -> 'th', 'en_gb' / 'en-UK' -> 'en-GB', 'zh-Hans' -> 'zh-CN', 'ja-JP' -> 'ja-JP'."""
    c = (code or "en").strip().replace("_", "-").lower()
    c = _ALIASES.get(c, c)
    parts = [p for p in c.split("-") if p]
    if not parts:
        return "en"
    base = _ALIASES.get(parts[0], parts[0])
    region = None
    for p in parts[1:]:
        if p == "hans":
            region = region or "cn"
        elif p == "hant":
            region = region or "tw"
        elif len(p) == 2 and p.isalpha():
            region = p
    if base == "en" and region == "uk":
        region = "gb"
    return base + (f"-{region.upper()}" if region else "")


def language_name(code: str) -> str:
    norm = normalize_locale(code)
    return REGION_NAMES.get(norm) or LANGUAGE_NAMES.get(norm.split("-")[0], code)


def available_locales() -> list[str]:
    """Locale codes with hand-written question phrasing (including regional overlays)."""
    out = []
    for p in resources.files("promptbridge.locales").iterdir():
        if p.name.endswith(".yaml"):
            stem = p.name[:-5]
            base, _, region = stem.partition("-")
            out.append(base + (f"-{region.upper()}" if region else ""))
    return sorted(out)


@lru_cache(maxsize=64)
def load_locale(code: str) -> Locale:
    pkg = "promptbridge.locales"
    norm = normalize_locale(code)
    base = norm.split("-")[0]
    files = {p.name[:-5] for p in resources.files(pkg).iterdir() if p.name.endswith(".yaml")}
    is_fallback = norm in _SCRIPT_FALLBACK or base not in files

    raw = dict(_read_yaml(pkg, "en.yaml" if is_fallback else f"{base}.yaml"))
    overlay_name = None
    if not is_fallback and norm != base and norm.lower() in files:
        overlay = _read_yaml(pkg, f"{norm.lower()}.yaml")
        overlay_name = overlay.get("name")
        raw["questions"] = {**raw.get("questions", {}), **overlay.get("questions", {})}
        for k, v in overlay.items():
            if k != "questions":
                raw[k] = v

    defaults = _read_yaml(pkg, "en.yaml")
    for key in _INSTRUCTION_KEYS:
        raw.setdefault(key, defaults[key])

    name = REGION_NAMES.get(norm) or overlay_name or LANGUAGE_NAMES.get(base) or raw.get("name") or norm
    style = _SCRIPT_FALLBACK.get(norm, "") if is_fallback else str(raw.get("style", "") or "")
    for key in _INSTRUCTION_KEYS:
        text = " ".join(str(raw[key]).split()).replace("{language}", name)
        raw[key] = f"{text} {style}".strip() if style else text

    raw.update(
        locale=norm,
        base=base,
        name=name,
        native_name=name if is_fallback else raw.get("native_name", name),
        style=style,
        is_fallback=is_fallback,
    )
    return Locale(**{k: raw[k] for k in Locale.model_fields if k in raw})
