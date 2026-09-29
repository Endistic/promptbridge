---
name: spec
description: Turn a request the user wrote in their own language (Thai by default) into a clear English task spec, ask only the questions that matter, then carry it out. Use when the user types /spec, or writes a coding request in Thai or another non-English language and wants it done properly.
---

# /spec — native-language request → English task spec → done

The user thinks in their own language. Your job is to turn what they wrote into a spec a coding
agent can execute without guessing, check it with them in their language, then do the work.
The `promptbridge` MCP server owns the structure (templates, which questions, rendering, memory).
You own the language work.

## Language rules (whole session)

- Talk to the user in their language (the `locale`; default Thai). Short sentences, plain words.
- Everything you send to the pb_* tools as `value_en` is **English**. Translate; never paste Thai into slots.
- Keep code, file paths, identifiers, commands, error messages and numbers exactly as they are.
- Technical terms with no common Thai word (API, endpoint, cache, deploy) stay in English inside Thai sentences.

## Steps

### 1. Capture
Call `pb_capture` with:
- `raw_text`: the user's request exactly as typed (everything after `/spec`)
- `locale`: `th` unless the user writes in another language (`ja`, `vi`, `id`, …)
- `cwd`: the current working directory

If the user wrote `/spec --quick …`, remember `quick=true` for step 3 and strip the flag from `raw_text`.

### 2. Fill slots (silently)
From `raw_text`, the returned `glossary_hits`, `repo_context` and — if it helps — a quick look at the
repo (Glob/Grep for the obvious files), fill the `slot_schema`:

```json
{"goal": {"value_en": "Lock a user account after repeated failed logins.", "status": "stated"},
 "behavior": {"value_en": ["Lock after 5 failures"], "status": "inferred"}}
```

- `stated` = the user actually said it. `inferred` = you guessed it (from context or code). Be honest; the
  server uses this to decide what to confirm.
- Omit slots you know nothing about. Do not invent requirements to look complete.
- Use glossary `term_en` names and real file paths you found.
- If `task_type` is clearly wrong (e.g. the user describes a bug but it guessed `feature`), pass the right
  one to `pb_clarify`.

### 3. Clarify (max 2 rounds)
Call `pb_clarify(session_id, slots, task_type?, quick?)`.

If `ready` is false, ask the returned `questions` with **AskUserQuestion** in one call:
- One question per item, in the user's language. Start from `prompt`, adapt it to this task.
- Give 2–4 concrete options that make sense for *this* code (e.g. "5 ครั้ง", "10 ครั้ง"), put the most
  likely first. The user can always type their own answer.
- `kind: "confirm"` → show your inferred value as the first option ("ใช่ ตามนี้") and alternatives after it.
- Keep headers ≤ 12 characters.

Translate the answers to English, update those slots with `status: "stated"`, and call `pb_clarify` again
with the full slot set. Stop when `ready` is true. If the user says "ไปเลย", "ข้ามได้", or similar,
call again with `quick: true`.

If AskUserQuestion is not available, ask in plain text as a numbered list with the options.

### 4. Compile and confirm
Call `pb_compile(session_id)`. Then show the user:

1. A 2–3 line summary in their language, following `summary_instruction`.
2. The assumptions, if any, as a short list in their language — these are the things they should check.
3. The English spec in a ```markdown code block, so they can glance at it.

Then ask with AskUserQuestion: **ลงมือเลย / แก้ไข spec / ยกเลิก** (in their language).

If `validation.warnings` mentions untranslated text, fix the slot and compile again before showing it.

### 5. Do the work
- **Approve** → treat `spec_markdown` as your task and carry it out. Follow its "How to work" section.
  Follow `reflect_instruction` for everything you say along the way: plans, questions and the final
  report are in the user's language; code stays as-is.
- **Edit** → apply the user's change to the spec (they may describe it in their language; you update the
  English), show the updated summary, confirm again. Record it as `edited` in step 6.
- **Cancel** → call `pb_save(outcome="rejected")` and stop.

### 6. Save and learn
After the work (or after cancel), call `pb_save(session_id, outcome, final_spec?)`:
- `accepted` if the spec was used as compiled, `edited` + `final_spec` if it changed, `rejected` if cancelled.
- If it returns `glossary_candidates`, match each to the word the user used in `raw_text`, then ask once:
  "จำคำเหล่านี้ไว้ไหม? «ตะกร้า» = `CartStore`". On yes, call `pb_glossary(action="add", …)`.
  Use `scope="repo"` (with `cwd`) for names specific to this codebase the team would share; otherwise `personal`.

## Other commands the user may ask for

- "จำคำนี้ไว้: X = Y" → `pb_glossary(action="add", term_native="X", term_en="Y", kind=...)`
- "ดูคำที่จำไว้" → `pb_glossary(action="list", cwd=...)` and show a small table.
- "เคยสั่งงานคล้าย ๆ นี้ไหม" → `pb_library(query=...)`; offer to reuse a result as the starting slots.

## Don't

- Don't ask more than the server returned, and never more than 2 rounds.
- Don't start coding before the user approves the spec (except task_type `explain`, which needs no approval).
- Don't show the English spec without the summary in their language.
