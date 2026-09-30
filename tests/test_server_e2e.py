"""Drives the real MCP server through an in-memory MCP client session."""

import json
from contextlib import asynccontextmanager

from promptbridge.server import mcp

try:  # SDK 2.x
    from mcp import Client

    @asynccontextmanager
    async def connect(server):
        async with Client(server) as c:
            yield c
except ImportError:  # SDK 1.x
    from mcp.shared.memory import create_connected_server_and_client_session

    @asynccontextmanager
    async def connect(server):
        async with create_connected_server_and_client_session(server._mcp_server) as c:
            yield c


def _is_error(res) -> bool:
    return bool(getattr(res, "is_error", None) or getattr(res, "isError", None))


async def call(client, tool, **args):
    res = await client.call_tool(tool, args)
    assert not _is_error(res), res.content[0].text
    return json.loads(res.content[0].text)


async def call_err(client, tool, **args):
    res = await client.call_tool(tool, args)
    assert _is_error(res)
    return res.content[0].text


async def test_tools_listed():
    async with connect(mcp) as client:
        names = {t.name for t in (await client.list_tools()).tools}
        assert names == {"pb_capture", "pb_clarify", "pb_compile", "pb_save", "pb_glossary", "pb_library"}


async def test_login_lockout_flow(repo):
    """The worked example from the spec, end to end."""
    async with connect(mcp) as c:
        # Teach the glossary one repo word first (repo scope → YAML file in the repo).
        await call(c, "pb_glossary", action="add", term_native="หน้า login", term_en="LoginPage",
                   kind="code_symbol", scope="repo", cwd=str(repo))
        assert (repo / ".promptbridge" / "glossary.yaml").exists()

        cap = await call(c, "pb_capture", raw_text="หน้า login อยากให้ถ้าใส่รหัสผิดหลายครั้งมันล็อคไว้ก่อน",
                         locale="th", cwd=str(repo / "api"))
        sid = cap["spec_id"]
        assert cap["task_type"] == "feature"
        assert cap["glossary_hits"][0]["term_en"] == "LoginPage"
        assert "FastAPI" in cap["repo_context"]["stack"]
        assert cap["repo_context"]["root"] == str(repo)

        # Host fills what it can: the count and lock duration are guesses.
        slots = {
            "goal": {"value_en": "Lock a user account after repeated failed login attempts.", "status": "stated"},
            "behavior": {"value_en": ["Lock after 5 failed attempts", "Lock lasts 15 minutes"], "status": "inferred"},
            "acceptance": {"value_en": ["Nth wrong password returns HTTP 423"], "status": "inferred"},
            "surface": {"value_en": "LoginPage and POST /auth/login", "status": "inferred"},
        }
        r1 = await call(c, "pb_clarify", spec_id=sid, slots=slots)
        assert r1["ready"] is False and r1["round"] == 1
        slots_asked = [q["slot"] for q in r1["questions"]]
        assert slots_asked[0] == "behavior" and r1["questions"][0]["kind"] == "confirm"
        assert len(slots_asked) <= 3

        # User answers: 5 times, 15 minutes, per account; don't touch token logic.
        slots["behavior"] = {"value_en": ["Count failures per account, not per IP.", "Lock after 5 consecutive failures.",
                                          "Lock lasts 15 minutes; a successful login resets the counter."],
                             "status": "stated"}
        slots["constraints"] = {"value_en": ["Do not change the existing session/token logic."], "status": "stated"}
        r2 = await call(c, "pb_clarify", spec_id=sid, slots=slots)
        assert r2["ready"] is True and r2["round"] == 1

        comp = await call(c, "pb_compile", spec_id=sid)  # uses stored slots
        md = comp["spec_markdown"]
        assert "## Requirements" in md and "Lock after 5 consecutive failures." in md
        assert "Do not change the existing session/token logic." in md
        assert "Do not change public APIs" not in md  # fallback replaced by the user's constraint
        assert '"หน้า login" = `LoginPage`' in md
        assert "Reply to the user in Thai" in comp["spec_markdown"]
        assert "Thai" in comp["summary_instruction"]
        assert comp["validation"]["missing_required"] == []

        # User edits the spec, naming a real service → glossary candidate.
        final = md.replace("Lock a user account", "Use `LoginAttemptService` to lock a user account")
        saved = await call(c, "pb_save", spec_id=sid, outcome="edited", final_spec=final)
        assert saved["glossary_candidates"] == ["LoginAttemptService"]
        assert saved["library_id"] == 1

        lib = await call(c, "pb_library", query="ล็อค")
        assert lib["results"][0]["library_id"] == 1
        full = await call(c, "pb_library", library_id=1)
        assert "LoginAttemptService" in full["spec"]["spec"]


async def test_task_type_override_and_round_cap():
    async with connect(mcp) as c:
        cap = await call(c, "pb_capture", raw_text="เปลี่ยนสีปุ่ม")
        sid = cap["spec_id"]
        r = await call(c, "pb_clarify", spec_id=sid, slots={}, task_type="bug_fix")
        assert not r["ready"]
        r = await call(c, "pb_clarify", spec_id=sid, slots={})
        assert not r["ready"] and r["round"] == 2
        r = await call(c, "pb_clarify", spec_id=sid, slots={})
        assert r["ready"] and "2 rounds" in r["reason"]
        comp = await call(c, "pb_compile", spec_id=sid)
        assert "## Assumptions" in comp["spec_markdown"]


async def test_personal_glossary_and_errors():
    async with connect(mcp) as c:
        await call(c, "pb_glossary", action="add", term_native="ตะกร้า", term_en="CartStore", kind="code_symbol")
        listed = await call(c, "pb_glossary", action="list")
        assert listed["terms"][0]["term_en"] == "CartStore"
        cap = await call(c, "pb_capture", raw_text="ตะกร้าไม่อัปเดตยอดรวม")
        assert cap["glossary_hits"][0]["scope"] == "personal"
        listed = await call(c, "pb_glossary", action="list")
        assert listed["terms"][0]["uses"] == 1

        assert "Unknown spec_id" in await call_err(c, "pb_compile", spec_id="nope")
        assert "Unknown task_type" in await call_err(c, "pb_capture", raw_text="x", task_type="deploy")
        assert "final_spec" in await call_err(c, "pb_save", spec_id=cap["spec_id"], outcome="edited")
        assert "needs cwd" in await call_err(c, "pb_glossary", action="add", term_native="a", term_en="b", scope="repo")


async def test_unsupported_locale_falls_back():
    async with connect(mcp) as c:
        cap = await call(c, "pb_capture", raw_text="ログイン画面にロック機能を追加したい", locale="ja")
        assert cap["locale"] == {"code": "ja", "language": "Japanese", "phrasing_available": False}
        r = await call(c, "pb_clarify", spec_id=cap["spec_id"], slots={})
        assert r["translate_questions_to"] == "Japanese"


async def test_no_tool_argument_named_session_id():
    """Some MCP bridges treat `session_id` as their own routing field and strip it."""
    async with connect(mcp) as c:
        for t in (await c.list_tools()).tools:
            schema = getattr(t, "input_schema", None) or getattr(t, "inputSchema", {})
            assert "session_id" not in schema.get("properties", {}), t.name
