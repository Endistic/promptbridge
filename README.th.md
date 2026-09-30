# promptbridge

**พิมพ์สั่งงาน AI coding เป็นภาษาไทย แล้วได้ task spec ภาษาอังกฤษที่ชัดเจน ให้ agent ทำงานได้โดยไม่ต้องเดา**

[English](README.md) · [Changelog](CHANGELOG.md) · [ร่วมพัฒนา](CONTRIBUTING.md)

```
/spec หน้า login อยากให้ถ้าใส่รหัสผิดหลายครั้งมันล็อคไว้ก่อน
```

1. ถามกลับเฉพาะจุดที่กำกวม ไม่เกิน 3 ข้อแบบกดเลือก เป็นภาษาไทย (ผิดกี่ครั้ง? ล็อคนานแค่ไหน? นับต่อ account หรือ IP?)
2. สรุปไทย 2–3 บรรทัดให้ตรวจ พร้อม spec อังกฤษ (Goal / Context / Requirements / Constraints / Acceptance criteria / Assumptions)
3. กด "ลงมือเลย" แล้ว agent ทำตาม spec และรายงานกลับเป็นไทย ส่วนโค้ด ชื่อไฟล์ และ error คงเป็นต้นฉบับ

สอนคำศัพท์ครั้งเดียว เช่น «ตะกร้า» = `CartStore` แล้ว spec ครั้งต่อ ๆ ไปจะใช้ชื่อจริงในโค้ดเอง

## ทำงานอย่างไร

| ส่วน | หน้าที่ |
| --- | --- |
| **Host model** (Claude หรือ LLM ที่คุณใช้อยู่) | อ่านภาษาไทย, เติม slot เป็นอังกฤษ, ถามคำถามเป็นไทย, สรุปผลเป็นไทย |
| **MCP server** (`promptbridge`, Python) | template ตาม task type, เลือกว่าจะถามอะไร, render spec แบบ deterministic, จำ glossary และ spec ที่เคยใช้ได้ผล |

Server ไม่เรียก LLM เอง จึงไม่มีค่า API เพิ่ม และข้อมูลทั้งหมดเก็บในเครื่องที่ `~/.promptbridge/`

## ติดตั้ง

ต้องมี [uv](https://docs.astral.sh/uv/) (`brew install uv`)

### Claude Code

```bash
# 1) ลงทะเบียน MCP server (ครั้งเดียว ใช้ได้ทุกโปรเจกต์)
claude mcp add promptbridge -s user -- uvx promptbridge-mcp

# 2) ติดตั้ง skill /spec
mkdir -p ~/.claude/skills/spec
curl -fsSL https://raw.githubusercontent.com/Endistic/promptbridge/main/skills/spec/SKILL.md \
  -o ~/.claude/skills/spec/SKILL.md

# 3) เปิด Claude Code ในโปรเจกต์ไหนก็ได้ แล้วพิมพ์
/spec ปุ่มบันทึกในหน้าโปรไฟล์กดแล้วขึ้น error 500
```

### Claude Desktop

เมนู **Claude** ที่แถบเมนูบนของ Mac → **Settings… → Developer → Edit Config** ใส่ config นี้ แล้วปิดแอปด้วย ⌘Q และเปิดใหม่

```json
{
  "mcpServers": {
    "promptbridge": { "command": "/opt/homebrew/bin/uvx", "args": ["promptbridge-mcp"] }
  }
}
```

ใส่ path เต็มจากคำสั่ง `which uvx` เพราะ Claude Desktop ไม่เห็น `PATH` ของ terminal จากนั้นพิมพ์ว่า "ใช้ promptbridge ทำ spec จากคำขอนี้: …"

### Cursor / client อื่นที่รองรับ MCP

```json
{ "mcpServers": { "promptbridge": { "command": "uvx", "args": ["promptbridge-mcp"] } } }
```

Client ที่ไม่มี skill จะทำตามขั้นตอนที่อธิบายไว้ใน tool แทน

### ติดตั้งจาก source

```bash
git clone https://github.com/Endistic/promptbridge
claude mcp add promptbridge -s user -- uvx --from ./promptbridge promptbridge
```

หรือโหลดเป็น Claude Code plugin (รวม server + skill): `claude --plugin-dir ./promptbridge` แล้วใช้ `/promptbridge:spec`

## คำสั่งที่ใช้บ่อย

| พิมพ์ | ผล |
| --- | --- |
| `/spec <ข้อความ>` | flow เต็ม: ถาม → สรุป → ลงมือ |
| `/spec --quick <ข้อความ>` | ข้ามคำถาม ช่องที่ไม่รู้จะถูกเขียนเป็น Assumptions ให้เห็น |
| "จำคำนี้ไว้: ตะกร้า = CartStore" | เพิ่ม glossary |
| "ดูคำที่จำไว้" | แสดง glossary ทั้งหมด |
| "เคยสั่งงานคล้าย ๆ นี้ไหม" | ค้น spec เก่าที่เคยใช้ได้ผล |

## Task types

`bug_fix` · `feature` · `refactor` · `test` · `explain` — แต่ละแบบมีข้อมูลที่ต้องมีต่างกัน (ดู `src/promptbridge/templates/*.yaml`) เพิ่ม type ใหม่ได้ด้วยไฟล์ YAML หนึ่งไฟล์

## Glossary

- **personal** — เก็บใน `~/.promptbridge/pb.db` ตามคุณไปทุกโปรเจกต์
- **repo** — เก็บใน `<repo>/.promptbridge/glossary.yaml` commit เข้า repo เพื่อให้ทั้งทีมใช้ศัพท์ชุดเดียวกัน

เมื่อคุณแก้ spec แล้วใส่ชื่อจริง (เช่น `LoginAttemptService`) ระบบจะเสนอให้จำคู่คำนั้นไว้ใช้ครั้งหน้า

## ภาษาอื่น

ออกแบบเป็น `locale` ตั้งแต่ต้น ตอนนี้มีคำถามสำเร็จรูปภาษาไทยและอังกฤษ ภาษาอื่น (ja, vi, id, ko, …) ใช้ได้เลยโดย host model แปลคำถามให้ เพิ่มภาษาใหม่ได้ด้วยไฟล์ `src/promptbridge/locales/<code>.yaml` หนึ่งไฟล์ ดู [CONTRIBUTING.md](CONTRIBUTING.md#add-a-language)

## ตั้งค่า

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
| --- | --- | --- |
| `PROMPTBRIDGE_HOME` | `~/.promptbridge` | ที่เก็บฐานข้อมูล |

ดูสถิติ accepted / edited / rejected ได้จาก MCP resource `promptbridge://stats` รองรับ MCP Python SDK ทั้ง 1.x และ 2.x

## License

[MIT](LICENSE)
