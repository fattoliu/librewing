from __future__ import annotations

import ast
import string
from pathlib import Path

from ssxng.i18n import _ZH_CN, _ZH_TW, _ZH_TW_OVERRIDES, system_language, tr


def test_simplified_chinese_from_lang(monkeypatch):
    monkeypatch.delenv("LANGUAGE", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert system_language() == "zh_CN"
    assert tr("Preferences…") == "偏好设置..."
    assert tr("PAC Auto Mode") == "PAC自动模式"
    assert tr("Imported {count} server(s).", count=2) == "已导入 2 个服务器配置。"


def test_traditional_chinese_from_language(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zh_TW:en_US")
    assert system_language() == "zh_TW"
    assert tr("Quit") == "結束"


def test_english_fallback(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "de_DE")
    assert system_language() == "en"
    assert tr("Global Mode") == "Global Mode"
    assert tr("Imported {count} server(s).", count=3) == "Imported 3 server(s)."


def test_unknown_key_falls_back_to_source(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zh_CN")
    assert tr("Future Menu Item") == "Future Menu Item"


def test_literal_translation_keys_have_both_chinese_translations():
    keys: set[str] = set()
    for path in Path("ssxng").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)

    assert keys <= _ZH_CN.keys()
    assert keys <= _ZH_TW.keys()


def test_traditional_chinese_does_not_inherit_simplified_only_text():
    language_neutral = {
        "ABP PAC engine URL",
        "Cancel",
        "Cipher",
        "External PAC URL:",
        "GFW List URL:",
        "GFWList URL",
        "SOCKS5",
        "Use GFWList",
    }
    assert _ZH_CN.keys() <= _ZH_TW_OVERRIDES.keys() | language_neutral


def test_translation_format_fields_match_source():
    formatter = string.Formatter()

    def fields(value: str) -> set[str]:
        return {name for _text, name, _spec, _conversion in formatter.parse(value) if name}

    for source in _ZH_CN:
        assert fields(_ZH_CN[source]) == fields(source)
        assert fields(_ZH_TW[source]) == fields(source)
