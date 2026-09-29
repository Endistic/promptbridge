# promptbridge

พิมพ์สั่งงาน AI coding เป็นภาษาไทย (หรือภาษาแม่ของคุณ) แล้วได้ task spec ภาษาอังกฤษที่ชัดเจน —
ถามกลับเฉพาะจุดที่กำกวม, ใช้ชื่อจริงใน codebase, และรายงานผลกลับเป็นภาษาไทย

```
/spec หน้า login อยากให้ถ้าใส่รหัสผิดหลายครั้งมันล็อคไว้ก่อน
```

→ ถาม 1–3 ข้อแบบกดเลือก (ผิดกี่ครั้ง? ล็อคนานแค่ไหน? นับต่อ account หรือ IP?)
→ สรุปไทย 2–3 บรรทัดให้ตรวจ + spec อังกฤษ (Goal / Context / Requirements / Constraints / Acceptance criteria / Assumptions)
→ กด "ลงมือเลย" แล้ว agent ทำตาม spec และรายงานเป็นไทย

## ทำงานอย่างไร

| ส่วน | หน้าที่ |
| --- | --- |
| **Host model** (Claude ใน Claude Code) | อ่านภาษาไทย, เติม slot เป็นอังกฤษ, ถามคำถามเป็นไทย, สรุปผลเป็นไทย |
| **MCP server** (`promptbridge`, Python) | template ตาม task type, เลือกว่าจะถามอะไร, render spec แบบ deterministic, จำ glossary และ spec ที่เคยใช้ได้ผล |

Server ไม่เรียก LLM เอง จึงไม่มีค่า API เพิ่ม — ใช้ model ที่คุณใช้อยู่แล้ว

## ติดตั้ง (Claude Code)

ต้องมี [uv](https://docs.astral.sh/uv/) และ Claude Code

```bash
# 1) ลงทะเบียน MCP server (ครั้งเดียว ใช้ได้ทุกโปรเจกต์)
claude mcp add promptbridge -s user -- uvx --from /path/to/promptbridge promptbridge

# 2) ติดตั้ง skill /spec
mkdir -p ~/.claude/skills && cp -r /path/to/promptbridge/skills/spec ~/.claude/skills/

# 3) เปิด Claude Code ในโปรเจกต์ไหนก็ได้ แล้วพิมพ์
/spec ปุ่มบันทึกในหน้าโปรไฟล์กดแล้วขึ้น error 500
```

หรือโหลดเป็น plugin (รวม server + skill) ตอนทดสอบ: `claude --plugin-dir /path/to/promptbridge` แล้วใช้ `/promptbridge:spec`

### Cursor / client อื่นที่รองรับ MCP

เพิ่มใน `~/.cursor/mcp.json`:

```json
{ "mcpServers": { "promptbridge": { "command": "uvx", "args": ["--from", "/path/to/promptbridge", "promptbridge"] } } }
```

Client ที่ไม่มี skill จะได้ flow จากคำอธิบาย tool ของ server แทน (ใช้ได้ แต่ skill ใน Claude Code ให้ประสบการณ์ดีกว่า)

## คำสั่งที่ใช้บ่อย

| พิมพ์ | ผล |
| --- | --- |
| `/spec <ข้อความ>` | flow เต็ม: ถาม → สรุป → ลงมือ |
| `/spec --quick <ข้อความ>` | ข้ามคำถาม ช่องที่ไม่รู้จะถูกเขียนเป็น Assumptions ให้เห็น |
| "จำคำนี้ไว้: ตะกร้า = CartStore" | เพิ่ม glossary |
| "ดูคำที่จำไว้" | แสดง glossary ทั้งหมด |
| "เคยสั่งงานคล้าย ๆ นี้ไหม" | ค้น spec เก่าที่เคยใช้ได้ผล |

## Task types

`bug_fix` · `feature` · `refactor` · `test` · `explain` — แต่ละแบบมี slot บังคับต่างกัน (ดู `src/promptbridge/templates/*.yaml`)
เพิ่ม type ใหม่ได้โดยเพิ่มไฟล์ YAML หนึ่งไฟล์

## Glossary

- **personal** — เก็บใน `~/.promptbridge/pb.db` ตามคุณไปทุกโปรเจกต์
- **repo** — เก็บใน `<repo>/.promptbridge/glossary.yaml` commit เข้า repo เพื่อให้ทั้งทีมใช้ศัพท์ชุดเดียวกัน

เมื่อคุณแก้ spec แล้วใส่ชื่อจริง (เช่น `LoginAttemptService`) ระบบจะเสนอให้จำคู่คำนั้นไว้ใช้ครั้งหน้า

## ภาษาอื่น

ออกแบบเป็น `locale` ตั้งแต่ต้น — ตอนนี้มีคำถามภาษาไทยและอังกฤษสำเร็จรูป ภาษาอื่น (ja, vi, id, ko, …)
ใช้ได้เลยโดย host model แปลคำถามให้ เพิ่มภาษาใหม่ได้ด้วยไฟล์ `src/promptbridge/locales/<code>.yaml` หนึ่งไฟล์

## พัฒนาต่อ

```bash
uv venv && uv pip install -e ".[dev]"
.venv/bin/pytest -q
```

ตั้ง `PROMPTBRIDGE_HOME` เพื่อย้ายที่เก็บฐานข้อมูล (ค่าเริ่มต้น `~/.promptbridge`)
ดูสถิติ accepted / edited / rejected ได้จาก MCP resource `promptbridge://stats`

รองรับ MCP Python SDK ทั้ง 1.x และ 2.x
