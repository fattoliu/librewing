# Roadmap

The goal is a dependable, community-maintained Ubuntu counterpart to the
ShadowsocksX-NG desktop workflow, not a line-for-line macOS port.

## 0.2 hardening

- [x] Protect credential-bearing files.
- [x] Repair CI, desktop dependency, and package smoke-test gaps.
- [x] Pin bundled simple-obfs artifacts.
- [x] Add HTTP/SOCKS bridge integration tests.
- [x] Prevent accidental unauthenticated LAN exposure.
- [x] Complete [hands-on GNOME testing](https://github.com/fattoliu/shadowsocksx-ng-linux/issues/10)
  on Ubuntu 24.04 and 26.04.
- [x] Publish the first signed prerelease packages.

## 0.3 architecture

- [x] Replace runtime monkey-patching with an explicit application controller.
- [x] Replace GTK3/AppIndicator with StatusNotifierItem and GTK4/libadwaita.
- [x] Add process supervision and structured runtime state/events.
- [x] Add automated GNOME proxy integration tests under a disposable session.

## 1.0 readiness

- [x] Define and test configuration migration guarantees.
- [x] Add deterministic SPDX SBOMs and signed public-release provenance.
- [x] Complete accessibility and Simplified Chinese/Traditional Chinese review.
- [x] Document support boundaries for non-GNOME desktops.
- [x] Maintain the [current release candidate](https://github.com/fattoliu/shadowsocksx-ng-linux/issues/10)
  without critical defects before 1.0.
