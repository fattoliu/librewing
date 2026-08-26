from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .backup import export_backup, restore_backup
from .config import CONFIG_FILE, LOG_FILE, AppConfig
from .health import format_health_report, run_health_checks
from .qr import export_profile_qr, scan_profile_qr
from .share import build_ss_url


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ssx-ng-tool",
        description="Diagnostics and maintenance utility for ShadowsocksX-NG Linux.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="check runtime dependencies, plugin and local ports")
    sub.add_parser("config-path", help="print the application config path")
    sub.add_parser("log-path", help="print the proxy log path")

    show = sub.add_parser("show-profile", help="print the active profile without exposing its password")
    show.add_argument("--json", action="store_true", help="emit JSON")

    url = sub.add_parser("show-url", help="print the active profile as an ss:// URL")
    url.add_argument("--unsafe", action="store_true", help="acknowledge that the URL contains credentials")

    qr_export = sub.add_parser("qr-export", help="export the active profile to a PNG QR code")
    qr_export.add_argument("output", type=Path)

    qr_import = sub.add_parser("qr-import", help="decode an ss:// QR image and add it as a server profile")
    qr_import.add_argument("image", type=Path)
    qr_import.add_argument("--no-activate", action="store_true", help="do not make the imported profile active")

    backup_export = sub.add_parser("backup-export", help="export all settings and server profiles")
    backup_export.add_argument("output", type=Path)

    backup_import = sub.add_parser("backup-import", help="replace local settings from a backup")
    backup_import.add_argument("input", type=Path)
    backup_import.add_argument("--yes", action="store_true", help="confirm replacement of the current config")

    return parser


def _safe_profile(config: AppConfig) -> dict[str, object]:
    data = asdict(config.profile)
    data["password"] = "***" if data.get("password") else ""
    return data


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = AppConfig.load()

    if args.command == "health":
        results = run_health_checks(config)
        print(format_health_report(results))
        failures = sum(not result.ok for result in results)
        print(f"\n{len(results) - failures} passed, {failures} failed")
        return 1 if failures else 0

    if args.command == "config-path":
        print(CONFIG_FILE)
        return 0

    if args.command == "log-path":
        print(LOG_FILE)
        return 0

    if args.command == "show-profile":
        data = _safe_profile(config)
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for key, value in data.items():
                print(f"{key}: {value}")
        return 0

    if args.command == "show-url":
        if not args.unsafe:
            print("Refusing to print a credential-bearing ss:// URL without --unsafe.", file=sys.stderr)
            return 2
        print(build_ss_url(config.profile))
        return 0

    if args.command == "qr-export":
        output = export_profile_qr(config.profile, args.output)
        print(output)
        return 0

    if args.command == "qr-import":
        profile = scan_profile_qr(args.image)
        config.profiles.append(profile)
        if not args.no_activate:
            config.active_profile = len(config.profiles) - 1
        config.save()
        print(f"Imported: {profile.name} ({profile.server}:{profile.server_port})")
        return 0

    if args.command == "backup-export":
        output = export_backup(config, args.output)
        print(output)
        print("Warning: this backup contains Shadowsocks server credentials.", file=sys.stderr)
        return 0

    if args.command == "backup-import":
        if not args.yes:
            print("Refusing to replace the current config without --yes.", file=sys.stderr)
            return 2
        restored = restore_backup(args.input)
        print(f"Restored {len(restored.profiles)} server profile(s).")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
