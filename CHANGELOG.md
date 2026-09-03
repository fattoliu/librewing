# Changelog

All notable changes are documented here. The format follows Keep a Changelog,
and releases use Semantic Versioning.

## [Unreleased]

### Added

- End-to-end tests for the local HTTP-to-SOCKS5 bridge.
- Explicit opt-in controls and warnings for LAN proxy listeners.
- Open-source contribution, security, conduct, architecture, and release docs.

### Changed

- Debian builds use the Ubuntu 24.04 runtime baseline for wider compatibility.
- CI installs and executes the generated Debian package.
- Health checks identify this application's listeners instead of accepting any
  process occupying the configured ports.

### Security

- Configuration, runtime, log, backup, and server-export files now use
  owner-only permissions.
- Bundled simple-obfs packages are verified against pinned SHA-256 checksums.
- The system proxy fails closed if the managed `ss-local` process exits.

## [0.2.0] - 2026-08-26

### Added

- Initial Linux desktop MVP with tray controls, PAC/global/manual modes,
  profiles, QR tooling, diagnostics, and Debian packaging.

