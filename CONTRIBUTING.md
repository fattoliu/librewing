# Contributing

Thank you for helping improve ShadowsocksX-NG Linux. Bug reports, Ubuntu
compatibility findings, documentation improvements, translations, tests, and
code contributions are welcome.

## Before opening an issue

1. Search existing issues.
2. Run `ssx-ng-tool health`.
3. Check the application log reported by `ssx-ng-tool log-path`.
4. Remove passwords and `ss://` URLs before posting diagnostics publicly.

Security vulnerabilities must follow [SECURITY.md](SECURITY.md) instead of a
public issue.

## Development setup

The desktop UI requires Ubuntu/Debian system packages:

```bash
sudo apt update
sudo apt install -y \
  python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
  gir1.2-dbusmenu-glib-0.4 libglib2.0-bin gsettings-desktop-schemas \
  shadowsocks-libev qrencode zbar-tools curl
python3 -m pip install -e '.[dev]'
```

Run the local quality gates before submitting a pull request:

```bash
python3 -m compileall -q ssxng
pytest -q --cov=ssxng --cov-branch --cov-report=term-missing
ruff check ssxng tests
bash -n scripts/*.sh
```

On Ubuntu, also exercise the actual GNOME proxy schema without touching your
desktop settings:

```bash
dbus-run-session -- env PYTHONPATH=. python3 scripts/smoke-gnome-proxy.py
bash scripts/smoke-gtk4.sh
```

Desktop and packaging changes should also be exercised on a clean supported
Ubuntu VM or container. See [docs/releasing.md](docs/releasing.md).

## Pull requests

- Keep each pull request focused and explain user-visible behavior.
- Add regression tests for fixes and tests for new non-UI behavior.
- Include screenshots for UI changes under both light and dark themes.
- Do not commit server credentials, QR codes, generated `.deb` files, logs, or
  local configuration.
- Use English Conventional Commits such as `fix(pac): preserve cached rules`.
- Use bullet points in commit bodies when a body is needed.

All contributions are accepted under GPL-3.0-or-later.
