# Security

Report vulnerabilities through [GitHub private vulnerability reporting](https://github.com/leo-kendall/pi-console/security/advisories/new). Do not put credentials or unredacted exploit details in a public issue.

Include the affected version, deployment setup, impact, reproduction steps and sanitized evidence. Useful reports include authorization bypass, cross-server credential routing, privilege expansion, file-area escape and deletion of unrelated resources. Only test systems you own or have permission to test.

Pi Console is intended for a trusted operator managing their own server. Pairing grants visibility and control within that backend's configured permissions. It does not provide separate tenant roles or per-user data isolation. Use HTTPS, restrict network access, and protect pairing credentials.

The current 0.5.0 beta is under active development. Fixes target the latest version; there is no separate long-term support branch. The project has not had an independent security audit.
