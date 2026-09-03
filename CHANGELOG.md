# Changelog

All notable changes are documented here. The format follows Keep a Changelog,
and releases use Semantic Versioning.

## [Unreleased]

### Added

- End-to-end tests for the local HTTP-to-SOCKS5 bridge.
- Explicit opt-in controls and warnings for LAN proxy listeners.
- Open-source contribution, security, conduct, architecture, and release docs.
- AppStream metadata, manual pages, and Debian policy validation for release
  packages.
- Disposable-session integration coverage for the real GNOME proxy schema.
- Virtual-display smoke coverage that constructs every GTK4 application window.
- Ubuntu 26.04 and Python 3.14 package compatibility coverage.

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

## [0.2.0] - 2026-08-26

### Added

- Initial Linux desktop MVP with tray controls, PAC/global/manual modes,
  profiles, QR tooling, diagnostics, and Debian packaging.
