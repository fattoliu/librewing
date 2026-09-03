# Roadmap

The goal is a dependable, community-maintained Ubuntu counterpart to the
ShadowsocksX-NG desktop workflow, not a line-for-line macOS port.

## 0.2 hardening

- [x] Protect credential-bearing files.
- [x] Repair CI, desktop dependency, and package smoke-test gaps.
- [x] Pin bundled simple-obfs artifacts.
- [x] Add HTTP/SOCKS bridge integration tests.
- [x] Prevent accidental unauthenticated LAN exposure.
- [ ] Complete hands-on GNOME testing on Ubuntu 24.04 and 26.04.
- [ ] Publish the first signed prerelease packages.

## 0.3 architecture

- [ ] Replace runtime monkey-patching with an explicit application controller.
- [ ] Consolidate legacy GTK3 dialogs into GTK4/libadwaita helpers.
- [ ] Add process supervision and structured runtime state/events.
- [ ] Add automated GNOME proxy integration tests under a disposable session.

## 1.0 readiness

- [ ] Define and test configuration migration guarantees.
- [ ] Add reproducible release provenance and a software bill of materials.
- [ ] Complete accessibility and Simplified Chinese/Traditional Chinese review.
- [ ] Document support boundaries for non-GNOME desktops.
- [ ] Maintain a release candidate without critical defects before 1.0.

