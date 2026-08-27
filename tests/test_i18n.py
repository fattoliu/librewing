from __future__ import annotations

from ssxng.i18n import system_language, tr


def test_simplified_chinese_from_lang(monkeypatch):
    monkeypatch.delenv("LANGUAGE", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert system_language() == "zh_CN"
    assert tr("Preferences…") == "偏好设置..."
    assert tr("PAC Auto Mode") == "PAC自动模式"


def test_traditional_chinese_from_language(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zh_TW:en_US")
    assert system_language() == "zh_TW"
    assert tr("Quit") == "結束"


def test_english_fallback(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "de_DE")
    assert system_language() == "en"
    assert tr("Global Mode") == "Global Mode"


def test_unknown_key_falls_back_to_source(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "zh_CN")
    assert tr("Future Menu Item") == "Future Menu Item"
