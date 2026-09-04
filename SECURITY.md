# Security Policy

## Supported versions

Until the first stable release, security fixes are made on the latest code in
the default branch. Older development snapshots are not supported.

## Reporting a vulnerability

Please use GitHub's private **Report a vulnerability** form in the repository
Security tab. Do not open a public issue for vulnerabilities or attach real
server credentials, `ss://` URLs, QR codes, configuration files, or logs.

Include the affected version or commit, Ubuntu version, reproduction steps,
impact, and any proposed mitigation. Maintainers aim to acknowledge a report
within seven days and will coordinate disclosure after a fix is available.

Likely security-sensitive areas include:

- credential and backup file permissions;
- proxy listeners exposed beyond loopback;
- PAC and GFWList downloads;
- SIP003 plugin resolution and execution;
- bundled binary provenance;
- process discovery and termination.

