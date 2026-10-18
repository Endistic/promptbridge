"""Every shipped locale is complete, and regional codes resolve the way users type them."""

import pytest

from promptbridge.catalog import (
    available_locales,
    get_template,
    guess_task_type,
    load_locale,
    load_templates,
    normalize_locale,
)
from promptbridge.clarify import select_questions
from promptbridge.models import SlotValue
from promptbridge.render import compile_spec

SHIPPED = ["th", "en", "en-GB", "en-AU", "ja", "zh", "es", "ru", "ar", "fr", "ko"]
ALL_SLOTS = sorted({s for t in load_templates().values() for s in t.slots})


def test_shipped_locales_present():
    assert set(SHIPPED) <= set(available_locales())


@pytest.mark.parametrize("code", SHIPPED)
def test_locale_has_every_question(code):
    loc = load_locale(code)
    assert not loc.is_fallback
    missing = [s for s in ALL_SLOTS if not loc.questions.get(s, "").strip()]
    assert missing == [], f"{code} lacks phrasing for {missing}"
    assert "{value}" in loc.confirm
    assert "{language}" not in loc.communication_line + loc.summary_instruction + loc.reflect_instruction


@pytest.mark.parametrize("code", [c for c in SHIPPED if not c.startswith("en")])
def test_questions_are_in_the_locale_language(code):
    """Base locales really have their own phrasing, not English copied in."""
    en = load_locale("en").questions
    loc = load_locale(code).questions
    same = [s for s in ALL_SLOTS if loc[s] == en[s]]
    assert same == []


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("th", "th"), ("TH", "th"), ("en", "en"), ("en_GB", "en-GB"), ("en-uk", "en-GB"),
        ("en-au", "en-AU"), ("ja-JP", "ja-JP"), ("jp", "ja"), ("kr", "ko"), ("zh-Hans", "zh-CN"),
        ("zh-Hant", "zh-TW"), ("zh_TW", "zh-TW"), ("es-419", "es"), ("", "en"), (None, "en"),
    ],
)
def test_normalize_locale(typed, expected):
    assert normalize_locale(typed) == expected


def test_regional_english_overlays():
    gb = load_locale("en-GB")
    assert gb.name == "English (UK)"
    assert "behaviour" in gb.questions["observed"]
    assert gb.questions["goal"] == load_locale("en").questions["goal"]  # inherited
    assert "British" in gb.communication_line
    assert gb.needs_communication_line
    au = load_locale("en-AU")
    assert "Australian" in au.communication_line
    assert not load_locale("en").needs_communication_line
    assert not load_locale("en-US").needs_communication_line


def test_region_without_overlay_inherits_base():
    mx = load_locale("es-MX")
    assert mx.name == "Spanish (Mexico)" and not mx.is_fallback
    assert mx.questions == load_locale("es").questions


def test_traditional_chinese_falls_back_with_script_hint():
    tw = load_locale("zh-TW")
    assert tw.is_fallback
    assert "Traditional Chinese" in tw.communication_line
    assert tw.questions == load_locale("en").questions  # host translates


def test_unknown_language_falls_back():
    vi = load_locale("vi")
    assert vi.is_fallback and vi.name == "Vietnamese"
    assert "Vietnamese" in vi.communication_line


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ログイン画面でボタンを押すとエラーになる", "bug_fix"),
        ("ログイン画面にパスワードリセット機能を追加したい", "feature"),
        ("登录页面点击按钮后报错 500", "bug_fix"),
        ("帮我解释一下 auth 模块是怎么工作的", "explain"),
        ("El botón de guardar no funciona y da error 500", "bug_fix"),
        ("Quiero añadir exportación a CSV en el informe", "feature"),
        ("Кнопка сохранения не работает, ошибка 500", "bug_fix"),
        ("Напиши тесты для функции calc_fee", "test"),
        ("زر الحفظ لا يعمل ويظهر خطأ 500", "bug_fix"),
        ("Le bouton enregistrer ne fonctionne pas, erreur 500", "bug_fix"),
        ("Peux-tu expliquer comment fonctionne le module auth ?", "explain"),
        ("저장 버튼을 누르면 에러가 나요", "bug_fix"),
        ("utils.py 를 기능별로 분리해서 리팩토링해 주세요", "refactor"),
    ],
)
def test_guess_task_type_per_language(text, expected):
    assert guess_task_type(text)[0] == expected


@pytest.mark.parametrize("code", SHIPPED)
def test_clarify_and_compile_in_every_locale(code):
    loc = load_locale(code)
    r = select_questions(get_template("bug_fix"), {}, loc, rounds_done=0)
    assert r.questions[0].prompt == loc.questions["goal"]
    res = compile_spec(get_template("feature"), {"goal": SlotValue(value_en="Add CSV export", status="stated")}, loc)
    has_line = loc.communication_line in res.spec_markdown
    assert has_line == loc.needs_communication_line


def test_untranslated_warning_for_non_latin_locales():
    t = get_template("feature")
    jp = compile_spec(t, {"goal": SlotValue(value_en="ログイン機能", status="stated")}, load_locale("ja"))
    assert any("untranslated" in w for w in jp.warnings)
    gb = compile_spec(t, {"goal": SlotValue(value_en="Add colour picker", status="stated")}, load_locale("en-GB"))
    assert not gb.warnings
