# Release process

1. Confirm `CHANGELOG.md` describes the release and remove unresolved critical
   items from the target milestone.
2. Run the local unit, coverage, lint, compile, and shell checks documented in
   `CONTRIBUTING.md`.
3. Build amd64 and arm64 packages in clean Ubuntu 24.04 environments.
4. Install each package with `apt`, import every desktop module, run
   `ssx-ng-tool health`, and execute the bundled `obfs-local` binary.
5. Manually exercise the README release checklist on GNOME under Ubuntu 24.04
   and 26.04, including recovery after killing `ss-local`.
6. Review `scripts/build-deb.sh` artifact URLs and SHA-256 values. Changing a
   URL requires an independently verified new checksum.
7. Merge only with all required CI checks green.
8. Create an annotated, signed `vMAJOR.MINOR.PATCH` tag from the default branch
   and push it. The package workflow publishes GitHub Release assets.
9. Download the published assets, verify architecture and checksums, and
   perform one final clean-machine installation.

Never publish packages produced from an uncommitted working tree or silently
reuse a binary found in the build machine's PATH. For an intentional local
binary override, set the explicit `SIMPLE_OBFS_BINARY` build variable and do
not use that build for an official release.

