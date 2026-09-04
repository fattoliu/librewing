# Release process

1. Confirm `CHANGELOG.md` describes the release and remove unresolved critical
   items from the target milestone.
2. Run the local unit, coverage, lint, compile, and shell checks documented in
   `CONTRIBUTING.md`.
3. Build amd64 and arm64 packages in clean Ubuntu 24.04 environments.
   Rebuild each revision once and compare the resulting files byte-for-byte.
4. Validate desktop metadata with `desktop-file-validate`, AppStream metadata
   with `appstreamcli validate --pedantic --no-net`, and the package with
   `lintian` without errors or warnings.
5. Generate the SPDX 2.3 SBOM with `scripts/generate-sbom.py`, verify that its
   package checksum matches the `.deb`, and compare a second generation
   byte-for-byte.
6. Install each package with `apt`, import every desktop module, run
   `ssx-ng-tool health`, and execute the bundled `obfs-local` binary.
7. Manually exercise the README release checklist on GNOME under Ubuntu 24.04
   and 26.04, including recovery after killing `ss-local`.
8. Review `scripts/build-deb.sh` artifact URLs and SHA-256 values. Changing a
   URL requires an independently verified new checksum.
9. Merge only with all required CI checks green.
10. Create an annotated, signed `vMAJOR.MINOR.PATCH[-PRERELEASE]` tag from the
    default branch and push it. The package workflow publishes GitHub Release
    assets and marks prerelease tags accordingly.
11. Download the published assets, verify architecture, SBOMs, and checksums, and
   perform one final clean-machine installation.

For tagged builds in a public repository, GitHub Actions creates Sigstore-backed
SLSA provenance and an SPDX SBOM attestation. Verify both predicates with:

```bash
gh attestation verify shadowsocksx-ng-linux_VERSION_ARCH.deb \
  --repo fattoliu/shadowsocksx-ng-linux
gh attestation verify shadowsocksx-ng-linux_VERSION_ARCH.deb \
  --repo fattoliu/shadowsocksx-ng-linux \
  --predicate-type https://spdx.dev/Document/v2.3
```

GitHub Free/Pro/Team only supports artifact attestations for public
repositories. The workflow intentionally skips attestation while the repository
is private so development builds remain usable before the open-source launch.

Never publish packages produced from an uncommitted working tree or silently
reuse a binary found in the build machine's PATH. For an intentional local
binary override, set the explicit `SIMPLE_OBFS_BINARY` build variable and do
not use that build for an official release.
