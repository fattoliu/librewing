from pathlib import Path


def test_dialog_action_area_has_consistent_edge_spacing():
    ui = Path("ssxng/ui.py").read_text(encoding="utf-8")
    assert ".dialog-action-area" in ui
    assert "padding: 8px 16px 16px 16px" in ui
    assert "min-width: 72px" in ui


def test_beta_entrypoint_installs_dialog_styles_before_creating_app():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    install_pos = beta.index("install_dialog_styles()")
    app_pos = beta.index("app = legacy_app.TrayApp()")
    assert install_pos < app_pos
