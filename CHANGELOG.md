# Changelog

## 0.5.0-beta.2

- Added a three-step setup guide: server address, device pairing and read-only feature checks.
- Added credential-free HTTPS diagnostics with DNS, certificate, timeout, redirect and endpoint hints.
- Kept manual pairing available for older backends without the diagnostic endpoint.
- Preserved unsaved addresses when refreshing settings and ignored outdated diagnostic responses.
- Clarified expired pairing codes and pairing retry limits.
- Added browser regressions for setup, stale requests and narrow-screen layouts.

Remote-desktop edge black regions remain unresolved. Desktop protocol support and physical keyboard support are unchanged.

## 0.5.0-beta.1

First public test release.

- Android app with an editable HTTPS endpoint and per-device pairing.
- Live system metrics, sampling history, alerts and a health summary.
- Automatic service/container discovery, configured controls and logs, and one-time confirmation to stop eligible running applications.
- Process memory/CPU views and guarded application termination.
- File uploads, downloads, renaming and trash/restore in an isolated directory.
- Optional GNOME Remote Login/RDP desktop with landscape fullscreen and adaptive resolution.
- Storage analysis, limited cache cleanup, configuration backup and custom application links.
- User-service installation and receipt-based removal of optional components.
- Local tests, GitHub Actions checks and Android development builds.

Known issues:

- Pointer movement to desktop edges/corners can produce a black area on some Android devices. Diagnostic sampling is included; the rendering issue is not fixed.
- Raspberry Pi OS VNC/WayVNC and hardware keyboard passthrough are not implemented.
- Test APKs use development signing. The app icon has separate, uncleared third-party branding rights.
