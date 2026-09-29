from promptbridge.catalog import get_template, guess_task_type, load_locale
from promptbridge.clarify import MAX_QUESTIONS, select_questions
from promptbridge.glossary import candidates_from_edit, match
from promptbridge.models import SlotValue
from promptbridge.render import compile_spec
from promptbridge.scanner import scan

TH = load_locale("th")


def sv(value, status="stated"):
    return SlotValue(value_en=value, status=status)


# ---- task type guess ---------------------------------------------------------

def test_guess_task_types():
    assert guess_task_type("ปุ่มบันทึกกดแล้วไม่ทำงาน error 500")[0] == "bug_fix"
    assert guess_task_type("ช่วยอธิบายว่า auth flow ทำงานยังไง")[0] == "explain"
    assert guess_task_type("เขียนเทสให้ฟังก์ชัน calc_fee")[0] == "test"
    assert guess_task_type("แยกไฟล์ utils ที่ยาวเกินไป")[0] == "refactor"
    assert guess_task_type("อยากให้หน้า login มีปุ่ม Google")[0] == "feature"
    assert guess_task_type("ทำอะไรสักอย่าง")[0] == "feature"  # no signal → feature


# ---- clarify -------------------------------------------------------------------

def test_required_missing_asked_first_and_capped():
    t = get_template("bug_fix")
    r = select_questions(t, {}, TH, rounds_done=0)
    assert not r.ready
    assert len(r.questions) == MAX_QUESTIONS
    assert [q.slot for q in r.questions] == ["goal", "observed", "expected"]
    assert all(q.kind == "missing" for q in r.questions)
    assert r.questions[0].prompt.startswith("สรุปเป้าหมาย")


def test_inferred_high_risk_is_confirmed_medium_is_not():
    t = get_template("feature")
    slots = {
        "goal": sv("Lock account after failed logins"),
        "behavior": sv(["Lock after 5 failures"], "inferred"),  # high risk → confirm
        "acceptance": sv(["5th failure returns 423"], "inferred"),  # medium → not asked
    }
    r = select_questions(t, slots, TH, rounds_done=0)
    kinds = {q.slot: q.kind for q in r.questions}
    assert kinds.get("behavior") == "confirm"
    assert "acceptance" not in kinds
    assert "Lock after 5 failures" in r.questions[0].prompt


def test_optional_gaps_only_fill_quota_never_block():
    t = get_template("feature")
    slots = {"goal": sv("x"), "behavior": sv(["y"]), "acceptance": sv(["z"])}
    r = select_questions(t, slots, TH, rounds_done=0)
    assert r.ready and r.questions == []


def test_stop_conditions():
    t = get_template("bug_fix")
    assert select_questions(t, {}, TH, rounds_done=2).ready
    assert select_questions(t, {}, TH, rounds_done=0, quick=True).ready
    assert select_questions(get_template("explain"), {}, TH, rounds_done=0).ready


def test_defaults_are_never_asked():
    t = get_template("refactor")
    slots = {"goal": sv("g"), "target": sv("api/"), "desired_structure": sv(["split"])}
    r = select_questions(t, slots, TH, rounds_done=0)
    assert r.ready  # behavior_preserved is required but has a default


def test_unknown_slot_warns_and_list_coerced():
    t = get_template("feature")
    r = select_questions(t, {"nope": sv("x"), "behavior": sv("single string")}, TH, 0)
    assert any("nope" in w for w in r.warnings)


# ---- render ----------------------------------------------------------------------

def test_render_feature_spec_shape():
    t = get_template("feature")
    slots = {
        "goal": sv("Lock a user account after 5 consecutive failed login attempts."),
        "behavior": sv(["Count failures per account.", "Lock for 15 minutes."]),
        "acceptance": sv(["5th wrong password returns HTTP 423."], "inferred"),
        "files": sv(["api/auth/login.py"], "inferred"),
    }
    res = compile_spec(t, slots, TH, {"stack": ["FastAPI", "React"]}, [
        {"term_native": "หน้า login", "term_en": "LoginPage", "kind": "code_symbol", "scope": "personal"}
    ])
    md = res.spec_markdown
    assert md.startswith("## Goal\nLock a user account")
    assert md.index("## Context") < md.index("## Requirements")
    assert "- Stack: FastAPI, React" in md
    assert "`api/auth/login.py`" in md
    assert "- [ ] 5th wrong password returns HTTP 423." in md
    assert '"หน้า login" = `LoginPage`' in md
    assert "Inferred from context, not stated by the user: Acceptance criteria." in md
    # Fallback constraint rendered even though the user gave none.
    assert "Do not change public APIs" in md
    assert "Reply to the user in Thai" in md
    assert not res.missing_required


def test_render_missing_required_becomes_assumption():
    res = compile_spec(get_template("bug_fix"), {"goal": sv("Fix save")}, TH)
    assert set(res.missing_required) == {"observed", "expected", "location"}
    assert res.spec_markdown.count("Not specified:") == 3
    # Default acceptance criteria are used.
    assert "- [ ] A regression test reproduces the bug" in res.spec_markdown


def test_render_warns_on_untranslated_text():
    res = compile_spec(get_template("feature"), {"goal": sv("ล็อค account")}, TH)
    assert any("untranslated" in w for w in res.warnings)


def test_render_is_deterministic():
    t = get_template("test")
    slots = {"goal": sv("g"), "code_under_test": sv("calc_fee"), "cases": sv(["a", "b"])}
    assert compile_spec(t, slots, TH).spec_markdown == compile_spec(t, slots, TH).spec_markdown


def test_english_locale_has_no_communication_line():
    res = compile_spec(get_template("feature"), {"goal": sv("g")}, load_locale("en"))
    assert "Reply to the user in" not in res.spec_markdown


def test_fallback_locale_names_language():
    ja = load_locale("ja")
    assert ja.is_fallback and "Japanese" in ja.communication_line


# ---- glossary --------------------------------------------------------------------

def test_match_longest_first_non_overlapping():
    terms = [
        {"term_native": "ตัวกรอง", "term_en": "Filter", "kind": "code_symbol", "scope": "personal"},
        {"term_native": "ตัวกรองราคา", "term_en": "PriceFilter", "kind": "code_symbol", "scope": "personal"},
    ]
    hits = match("แก้ตัวกรองราคาให้เร็วขึ้น", terms)
    assert [h["term_en"] for h in hits] == ["PriceFilter"]
    hits = match("ตัวกรองราคา กับ ตัวกรอง", terms)
    assert {h["term_en"] for h in hits} == {"PriceFilter", "Filter"}


def test_candidates_from_edit():
    compiled = "## Goal\nFix the price filter in `web/src/Filter.tsx`."
    final = "## Goal\nFix `PriceFilter` in `web/src/Filter.tsx` using price_range_store."
    assert candidates_from_edit(compiled, final, known_en=set()) == ["PriceFilter", "price_range_store"]
    assert candidates_from_edit(compiled, final, known_en={"PriceFilter"}) == ["price_range_store"]


# ---- scanner ---------------------------------------------------------------------

def test_scan_monorepo(repo):
    r = scan(repo)
    assert {"Python", "FastAPI", "SQLAlchemy", "React", "TypeScript"} <= set(r["stack"])
    assert {"pytest", "Vitest"} <= set(r["test_frameworks"])
    assert "api/" in r["top_level"] and "web/" in r["top_level"]
