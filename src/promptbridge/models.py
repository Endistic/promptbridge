from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

SlotStatus = Literal["stated", "inferred", "missing"]
Risk = Literal["high", "medium", "low"]
SlotKind = Literal["text", "list"]
SectionStyle = Literal["paragraph", "bullets", "numbered", "checklist", "code"]
Outcome = Literal["accepted", "edited", "rejected"]

SlotContent = Union[str, list[str], None]


class SlotValue(BaseModel):
    """A slot as filled in by the host model.

    value_en is always English (the host translates from the user's language).
    status says where the value came from:
      stated   — the user said it (in their message or an answer)
      inferred — the host guessed it from context
      missing  — nobody knows yet
    """

    value_en: SlotContent = None
    status: SlotStatus = "missing"

    def is_empty(self) -> bool:
        v = self.value_en
        if v is None:
            return True
        if isinstance(v, str):
            return not v.strip()
        return not any(str(x).strip() for x in v)


class SlotSpec(BaseModel):
    name: str
    description: str
    kind: SlotKind = "text"
    required: bool = False
    risk: Risk = "medium"
    default: SlotContent = None
    fallback: SlotContent = None  # rendered when missing, but the slot may still be asked about


class Section(BaseModel):
    title: str
    slots: list[str]
    style: SectionStyle = "paragraph"


class TaskTemplate(BaseModel):
    task_type: str
    title: str
    ask: bool = True
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    slots: dict[str, SlotSpec]
    sections: list[Section]
    instructions: list[str] = Field(default_factory=list)


class Locale(BaseModel):
    locale: str
    name: str
    native_name: str
    questions: dict[str, str]
    confirm: str
    summary_instruction: str
    reflect_instruction: str
    communication_line: str
    is_fallback: bool = False  # True when we used English phrasing for an unsupported locale


class Question(BaseModel):
    slot: str
    kind: Literal["missing", "confirm"]
    prompt: str  # default phrasing in the user's language (or English + translate hint)
    slot_description: str  # English, for the host
    slot_kind: SlotKind
    current_value: SlotContent = None
