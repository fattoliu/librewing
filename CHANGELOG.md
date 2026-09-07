# Changelog

All notable changes are documented here. The format follows Keep a Changelog,
and releases use Semantic Versioning.

## [Unreleased]

## [0.3.0-rc.2] - 2026-09-07

### Changed

- Pull requests run one CI suite instead of duplicate push and pull-request runs.

### Fixed

- Editing custom PAC rules now changes the PAC URL revision immediately, avoiding
  stale GNOME/Chromium cache without restarting `ss-local`.
- Custom PAC rules can be disabled without deletion by using the documented
  `! disabled:` prefix.

## [0.3.0-rc.1] - 2026-09-07

### Added

- End-to-end tests for the local HTTP-to-SOCKS5 bridge.
- Explicit opt-in controls and warnings for LAN proxy listeners.
- Open-source contribution, security, conduct, architecture, and release docs.
- AppStream metadata, manual pages, and Debian policy validation for release
  packages.
- Disposable-session integration coverage for the real GNOME proxy schema.
- Virtual-display smoke coverage that constructs every GTK4 application window.
- Ubuntu 26.04 and Python 3.14 package compatibility coverage.
- Deterministic SPDX 2.3 SBOMs for every Debian release artifact.
- Sigstore-backed SLSA provenance and signed SBOM attestations for tagged
  public releases.

### Changed

- The desktop stack is GTK4/libadwaita-only; the tray now uses the standard
  StatusNotifierItem and DBusMenu protocols instead of GTK3/AppIndicator.
- Configuration files now carry a schema version; legacy files migrate safely,
  and files created by newer releases are never overwritten.
- Debian builds use the Ubuntu 24.04 runtime baseline for wider compatibility.
- CI installs and executes the generated Debian package.
- Health checks identify this application's listeners instead of accepting any
  process occupying the configured ports.
- PAC files and rule downloads use the configured SOCKS listener, including
  LAN and IPv6 addresses.
- Debian artifacts are reproducible for a fixed source revision and include
  portable SHA-256 checksum files.

### Security

- Configuration, runtime, log, backup, and server-export files now use
  owner-only permissions.
- Exporting credentials no longer changes permissions on the selected parent
  directory.
- Instance locks and exported profile QR images now use owner-only permissions.
- Bundled simple-obfs packages are verified against pinned SHA-256 checksums.
- The system proxy fails closed if the managed `ss-local` process exits.
- Structured runtime supervision restarts PAC/HTTP services and reports
  failure/recovery transitions without repeated alerts.

### Fixed

- StatusNotifier hosts can render bundled paper-plane and P/G/M icons from
  exported pixel data when desktop icon-theme lookup misses newly installed icons.
- The off-state paper plane uses a legible medium gray instead of a low-opacity
  dark asset that disappeared against GNOME's panel.

## [0.2.0] - 2026-08-26

### Added

- Initial Linux desktop MVP with tray controls, PAC/global/manual modes,
  profiles, QR tooling, diagnostics, and Debian packaging.
