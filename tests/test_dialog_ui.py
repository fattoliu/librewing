from pathlib import Path


def test_dialog_action_area_has_consistent_edge_spacing_and_rounding():
    ui = Path("ssxng/ui.py").read_text(encoding="utf-8")
    assert ".dialog-action-area" in ui
    assert "padding: 10px 18px 16px 18px" in ui
    assert "min-width: 88px" in ui
    assert "border-bottom-left-radius: 12px" in ui
    assert "border-bottom-right-radius: 12px" in ui
    assert "window.dialog decoration" in ui


def test_custom_dialogs_use_common_polish_helper():
    for path in ("ssxng/preferences_ng.py", "ssxng/server_manager.py", "ssxng/share_dialog.py"):
        source = Path(path).read_text(encoding="utf-8")
        assert "polish_dialog" in source


def test_beta_entrypoint_installs_dialog_styles_before_creating_app():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    install_pos = beta.index("install_dialog_styles()")
    app_pos = beta.index("app = legacy_app.TrayApp()")
    assert install_pos < app_pos
